"""唯一对业务层暴露的在线摘要流水线：SummaryPipeline。

串联（docs/ARCHITECTURE.md 第 5 节）：
    文本清洗 → 中文分句 → BERT 句向量 → 余弦相似度 → TextRank/PageRank
    → Token Budget → 原文顺序恢复 → Seq2Seq Transformer → 最终摘要

公共接口已冻结，不得修改：
    SummaryResult(summary, generation_time_ms, model_version)
    SummaryPipeline.load() / generate(article) -> SummaryResult

generate() 计时从方法进入到最终摘要字符串完成，不含模型下载/首次加载/
新闻抓取/HTTP/MySQL（见 REQUIREMENTS NFR-07）。
正式模型未交付时，load()/generate() 抛 AiUnavailableError，绝不伪造摘要。
"""

from __future__ import annotations

import time

from app.ai.bert_encoder import BertEncoder
from app.ai.postprocess import normalize_summary
from app.ai.preprocess import clean_text, split_sentences
from app.ai.summarizer import AiUnavailableError, TransformerSummarizer
from app.ai.textrank import rank_sentences, select_sentences_by_budget

# 常量定义与术语映射（docs/ARCHITECTURE.md 第 4 节）：
# max_source_length = max_input_tokens、max_target_length = max_new_tokens。
from dataclasses import dataclass


class InputTooLongError(AiUnavailableError):
    """输入正文超过正式模型最大输入 token 数（AI 不可用类，可被调用方识别）。"""


@dataclass(frozen=True)
class SummaryResult:
    """一次真实摘要生成的标准结果。"""

    summary: str
    generation_time_ms: int
    model_version: str


class SummaryPipeline:
    """串联预处理、BERT、TextRank、Token Budget 与摘要模型的在线流水线。"""

    def __init__(
        self,
        *,
        bert_model_name: str = "google-bert/bert-base-chinese",
        model_dir: str = "runtime/models/news_summarizer",
        max_input_tokens: int = 512,
        max_new_tokens: int = 100,
        char_per_token: float = 2.0,
    ) -> None:
        """按冻结组件构造流水线；组件惰性加载，直到 load() 才真正实例化模型。"""
        self.bert_model_name = bert_model_name
        self.model_dir = model_dir
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
        """加载并预热正式在线摘要组件（BERT、TextRank、正式 Transformer）。

        顺序与架构一致：先加载句向量 BERT，再加载 B 交付的正式摘要模型。
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
        # Token Budget 使用正式模型上限（映射 max_input_tokens）
        self.max_input_tokens = formal_max_input
        self.max_new_tokens = formal_max_new
        self.model_version = self.summarizer.model_version

        # 4. 预热（可选）：跑一个最小句序列，确保 GPU 上 CUDA 图/内核已就绪
        self._warmup()

        self._loaded = True

    def _warmup(self) -> None:
        """预热流水线（空实现骨架，正式模型交付后在此做真实预热）。"""
        return None

    def generate(self, article: str) -> SummaryResult:
        """为一篇新闻正文生成真实摘要结果。

        - article：D 经网页级清洗后的真实正文字符串。
        - 返回：summary / generation_time_ms（毫秒）/ model_version。
        全链路必须包含 BERT、TextRank、Token Budget、Seq2Seq，不固定 Top-N。
        """
        if not self._loaded:
            raise AiUnavailableError("SummaryPipeline 尚未 load()，请先加载正式组件。")
        start_ns = time.perf_counter_ns()
        try:
            summary = self._generate_summary(article)
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
        # 1.1 输入长度预检：超过正式模型最大输入 token 的新闻不生成摘要
        # （超长新闻实测摘要质量/正确率低，团队统一约定直接拒绝，不送入后续流程）
        input_tokens = self.bert.count_tokens(cleaned)
        if input_tokens > self.max_input_tokens:
            raise InputTooLongError(
                f"输入正文过长：{input_tokens} token，超过正式模型最大输入 {self.max_input_tokens} token。"
            )
        # 2. 中文分句
        sentences = split_sentences(cleaned)
        if not sentences:
            raise AiUnavailableError("输入正文无法切分出有效句子，无法生成摘要。")
        # 3. BERT 句向量
        vectors = self.bert.encode_batch(sentences)
        # 4. TextRank 得分
        scores = rank_sentences(vectors)
        # 5. Token Budget 选句（贪心填预算、超长句切分、恢复原序）
        selected_idx = select_sentences_by_budget(
            sentences,
            scores,
            max_input_tokens=self.max_input_tokens,
            char_per_token=self.char_per_token,
        )
        if not selected_idx:
            raise AiUnavailableError("Token Budget 未选出任何句子，无法生成摘要。")
        # 6. 按原文顺序拼回送入正式 Transformer
        selected_text = "".join(sentences[i] for i in selected_idx)
        # 7. 正式 Seq2Seq 生成最终摘要
        summary = self.summarizer.generate(selected_text)
        if not summary:
            raise AiUnavailableError("正式摘要模型输出为空，无法生成摘要。")
        # 8. 输出规范化：修复模型输出的排版问题（空格/标点/百分号格式），不改事实
        return normalize_summary(summary)
