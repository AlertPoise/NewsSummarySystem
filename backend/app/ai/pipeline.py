"""唯一对业务层暴露的在线摘要流水线接口。

串联（docs/ARCHITECTURE.md 第 5 节）：
    文本清洗 → 中文分句 → BERT 句向量 → 余弦相似度 → TextRank/PageRank
    → Token Budget → 原文顺序恢复 → Seq2Seq Transformer → 最终摘要

公共接口已冻结，不得修改：
    SummaryResult(summary, generation_time_ms, model_version)
    SummaryPipeline.load() / generate(article) -> SummaryResult
"""

from __future__ import annotations

import time
from pathlib import Path

from app.ai.bert_encoder import BertEncoder
from app.ai.postprocess import normalize_summary
from app.ai.preprocess import clean_text, split_sentences
from app.ai.summarizer import AiUnavailableError, TransformerSummarizer
from app.ai.textrank import rank_sentences, select_sentences_by_budget
from app.config import get_settings

# 契约再导出：与 app.exceptions 共享同一 InputTooLongError，保证
# `from app.ai.pipeline import InputTooLongError` 与
# `from app.exceptions import InputTooLongError` 拿到同一个类
# （D Worker 捕获的正是 app.exceptions 这份）。
from app.exceptions import InputTooLongError  # noqa: F401

from dataclasses import dataclass


@dataclass(frozen=True)
class SummaryResult:
    """一次真实摘要生成的标准结果。"""

    summary: str
    generation_time_ms: int
    model_version: str


def _resolve_model_dir() -> str:
    """解析正式模型目录为绝对路径。

    以 backend/ 为基准解析 config.model_dir（形如 "../runtime/models"），
    再拼 news_summarizer。避免 C 单测（从仓库根跑）与 D Worker
    （从 backend 跑）因相对 cwd 不同而找不到模型。
    """
    settings = get_settings()
    # pipeline.py 位于 <repo>/backend/app/ai/，parents[2] 即 <repo>/backend
    backend_dir = Path(__file__).resolve().parents[2]  # <repo>/backend
    model_root = (backend_dir / settings.model_dir).resolve()
    return str(model_root / "news_summarizer")


class SummaryPipeline:
    """串联预处理、BERT、TextRank、Token Budget 与摘要模型的在线流水线。"""

    def __init__(
        self,
        *,
        bert_model_name: str | None = None,
        model_dir: str | None = None,
        max_input_tokens: int = 512,
        max_new_tokens: int = 100,
        char_per_token: float = 2.0,
    ) -> None:
        """按冻结组件构造流水线；组件惰性加载，直到 load() 才真正实例化模型。

        model_dir 缺省时用统一配置解析（backend 相对 ../runtime/models/news_summarizer），
        不依赖当前工作目录。
        """
        settings = get_settings()
        self.bert_model_name = bert_model_name or settings.bert_model_name or "google-bert/bert-base-chinese"
        self.model_dir = model_dir or _resolve_model_dir()
        self.max_input_tokens = max_input_tokens
        self.max_new_tokens = max_new_tokens
        self.char_per_token = char_per_token
        self.bert: BertEncoder | None = None
        self.summarizer: TransformerSummarizer | None = None
        self._loaded = False
        self.model_version = ""

    @property
    def is_loaded(self) -> bool:
        """是否已完成组件加载与预热。"""
        return self._loaded

    def load(self) -> None:
        """加载并预热正式在线摘要组件（BERT、正式 Transformer）。

        顺序与架构一致：先加载句向量 BERT，再加载正式摘要模型。
        任一组件的正式交付缺失都抛 AiUnavailableError，不静默降级。
        """
        # 1. BERT 句向量编码器
        self.bert = BertEncoder(model_name=self.bert_model_name)
        self.bert.load()

        # 2. 正式 Seq2Seq Transformer（读 B 交付目录的 model_metadata.json）
        self.summarizer = TransformerSummarizer(model_dir=self.model_dir)
        self.summarizer.load()

        # 3. 读取正式参数并完成一致性校验（不允许 C 私自缩短输入）
        metadata = self.summarizer.metadata
        formal_max_input = int(metadata["max_input_tokens"])
        formal_max_new = int(metadata["max_new_tokens"])
        if formal_max_input <= 0 or formal_max_new <= 0:
            raise AiUnavailableError("正式模型元信息中 max_input_tokens / max_new_tokens 非法。")
        self.max_input_tokens = formal_max_input
        self.max_new_tokens = formal_max_new
        self.model_version = self.summarizer.model_version

        # 4. 预热：跑一个最小样本，确保 GPU CUDA 内核/缓存已就绪
        self._warmup()

        self._loaded = True

    def _warmup(self) -> None:
        """预热流水线：真实跑一次最小生成，触发 GPU 内核编译与缓存。"""
        try:
            warm_text = "今日发布经济数据，运行总体平稳。市场预期逐步改善。"
            # 直接调 summarize 单句，避免完整 pipeline 依赖外部组件顺序
            if self.summarizer is not None and self.summarizer.is_loaded:
                self.summarizer.generate(warm_text)
            if self.bert is not None and self.bert.is_loaded:
                self.bert.encode_batch(["今日发布经济数据，运行总体平稳。"])
        except Exception:
            # 预热失败不阻断加载（正式推理时仍可尝试）
            pass

    def generate(self, article: str) -> SummaryResult:
        """为一篇新闻正文生成真实摘要结果。

        正文超过冻结 max_input_tokens 时抛 InputTooLongError：属确定性
        永久不可处理（D Worker 据此删除），区别于临时性生成失败。
        """
        if not self._loaded:
            raise AiUnavailableError("SummaryPipeline 尚未 load()，请先加载正式组件。")
        start_ns = time.perf_counter_ns()
        try:
            summary = self._generate_summary(article)
        except InputTooLongError:
            # 正文超长：确定性不可处理，原样抛出（不得包成 AiUnavailableError，
            # 否则 D Worker 的 except InputTooLongError 捕获不到）
            raise
        except AiUnavailableError:
            raise
        except Exception as exc:  # 任何真实失败都向上抛，不返回假摘要
            raise AiUnavailableError(f"摘要生成失败：{exc}") from exc
        finally:
            elapsed_ms = (time.perf_counter_ns() - start_ns) / 1_000_000
        return SummaryResult(
            summary=summary,
            generation_time_ms=int(elapsed_ms),
            model_version=self.model_version,
        )

    def _generate_summary(self, article: str) -> str:
        """执行全链路生成，返回最终摘要字符串。"""
        # 1. NLP 级清洗
        cleaned = clean_text(article)
        if not cleaned:
            raise AiUnavailableError("输入正文清洗后为空，无法生成摘要。")
        # 1.1 输入长度预检：用正式摘要模型 tokenizer 精确计数（非 BERT tokenizer）
        #     （项目冻结：正式 T5 tokenizer 计数；> max_input_tokens 明确拒绝）
        if self.summarizer is not None:
            input_tokens = self.summarizer.count_tokens(cleaned)
            if input_tokens > self.max_input_tokens:
                raise InputTooLongError(
                    f"输入正文过长：{input_tokens} token，超过正式模型最大输入 {self.max_input_tokens} token。"
                )
        # 2. 中文分句
        sentences = split_sentences(cleaned)
        if not sentences:
            raise AiUnavailableError("输入正文无法切分出有效句子，无法生成摘要。")
        # 3. BERT 句向量
        if self.bert is None:
            raise AiUnavailableError("BERT 编码器未加载。")
        vectors = self.bert.encode_batch(sentences)
        # 4. TextRank 得分
        scores = rank_sentences(vectors)
        # 5. Token Budget 选句（贪心填预算、恢复原序；返回可直接拼接的文本片段）
        selected_texts = select_sentences_by_budget(
            sentences,
            scores,
            max_input_tokens=self.max_input_tokens,
            char_per_token=self.char_per_token,
        )
        if not selected_texts:
            raise AiUnavailableError("Token Budget 未选出任何句子，无法生成摘要。")
        # 6. 拼回送入正式 Transformer（内容即预算对象，无 silent truncation）
        selected_text = "".join(selected_texts)
        # 7. 正式 Seq2Seq 生成最终摘要
        if self.summarizer is None:
            raise AiUnavailableError("正式摘要模型未加载。")
        summary = self.summarizer.generate(selected_text)
        if not summary:
            raise AiUnavailableError("正式摘要模型输出为空，无法生成摘要。")
        # 8. 输出规范化：修复模型输出的排版问题（空格/标点/百分号格式），不改事实
        normalized = normalize_summary(summary)
        # 9. 硬事实一致性检查：摘要中的硬事实(百分比/时间/年份)须能在源文找到依据
        from app.ai.postprocess import check_factual_consistency

        violations = check_factual_consistency(normalized, cleaned)
        if violations:
            raise AiUnavailableError(
                f"摘要硬事实校验未通过，不交付：{'；'.join(violations)}"
            )
        return normalized
