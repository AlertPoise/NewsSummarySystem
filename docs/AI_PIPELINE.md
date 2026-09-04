# AI 流水线与接口冻结

在线步骤固定为：`article → clean_text → split_sentences → BERT 批量句向量 → 余弦相似度图 → TextRank/PageRank → max_input_tokens 关键句选择 → 原文顺序恢复 → Seq2Seq Transformer → SummaryResult`。

`clean_text(text: str) -> str` 负责标准化和噪声字符处理；`split_sentences(text: str) -> list[str]` 负责中文分句与长度基本检查。BERT 使用最终确定的 Hugging Face checkpoint，只加载一次、支持 GPU、批量编码并处于 inference_mode/no_grad。TextRank 按 BERT 语义向量的余弦相似度建图，输出同序的重要性分数。关键句按分数纳入 Transformer 的 `max_input_tokens`，不得固定 Top-N，随后按原位置还原。

对业务层冻结如下接口：

```python
@dataclass(frozen=True)
class SummaryResult:
    summary: str
    generation_time_ms: int
    model_version: str

class SummaryPipeline:
    def load(self) -> None: ...
    def generate(self, article: str) -> SummaryResult: ...
```

`load()` 在进程启动或 Worker 初始化时加载、预热；`generate()` 从方法进入开始到最终摘要字符串得到结束计时。模型权重读取 `runtime/models/news_summarizer/`，不得下载、在线训练或绕过 BERT/TextRank。C 在阶段 2 实现在线组件，B 在阶段 2 提供唯一正式模型、CNewSum 评价和基准；目标为 ROUGE-L ≥ 0.40、预热后单篇少于 1.5 秒。
