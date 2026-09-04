# 系统架构与跨模块接口冻结

## 1. 总体架构与依赖方向

```text
真实新闻网站
      ↓
Crawler [D] → RawArticle → NewsService [D] → MySQL [A维护Schema]
                                             ↓
HarmonyOS [E] ← FastAPI Route [A/D] → SummaryService [D] → SQLAlchemy / MySQL
                                             ↑                   ↑
                                        Worker [D] ──────────────┘
                                             ↓
                                    SummaryPipeline [C]
                                    ↓ BERT → TextRank → Seq2Seq Transformer
                                                         ↑
                                     B 离线训练、评价并交付正式模型
```

依赖只能沿图中方向传递：`Crawler → NewsService → MySQL`、`API → SummaryService → SQLAlchemy`、`Worker → SummaryService → SQLAlchemy`、`Worker → SummaryPipeline`、`HarmonyOS → FastAPI`。禁止 API Route 直接写数据库业务、操作 BERT/TextRank 或调用 `model.generate`；禁止 SummaryService 持有或调用 SummaryPipeline；禁止 Crawler 调用 AI；禁止 AI 模块操作收藏或新闻业务数据库；禁止 HarmonyOS 访问 MySQL 或 Python AI。

## 2. 模块职责

| 模块 | 负责人 | 输入 | 输出 | 禁止事项 |
|---|---|---|---|---|
| Crawler | D | 真实网站页面或合规公开接口 | RawArticle | 输出虚构新闻、调用 AI |
| NewsService | D | RawArticle、查询参数 | 新闻记录、分类、分页、详情 | 依赖具体来源类型 |
| 数据库公共层 | A | SQLAlchemy Schema/会话约定 | 四张核心表规范 | 修改 D 的业务规则 |
| SummaryPipeline | C | article 字符串 | SummaryResult | 改动公共接口、写业务表 |
| SummaryService | D | news_id、新闻记录、当前 summary_status、SummaryResult 或错误信息 | 任务领取结果、状态和持久化结果 | 持有或调用 Pipeline、BERT、TextRank、Transformer |
| Worker | D | SummaryService 领取的 processing 新闻、SummaryPipeline | SummaryResult 或失败信息 | 绕过 SummaryService 另建状态机 |
| 模型训练与评价 | B | CNewSum、训练配置 | 正式模型和评价交付物 | 修改新闻业务表 |
| 用户业务 | A | client_id、news_id、helpful | 收藏、反馈、用户状态 | 复制 D 的新闻查询逻辑 |
| HarmonyOS | E | REST 响应 | 页面与交互状态 | 访问 MySQL/Python AI |

## 3. 完整数据流

1. D 的 Crawler 从真实来源解析网页，执行网页级清洗并返回 RawArticle。
2. D 的 NewsService 映射六类、计算正文 SHA-256、去重并写入 `news_articles`，摘要状态为 `pending`。
3. D 的 Worker 通过 SummaryService 原子取得 pending 新闻，状态变为 `processing`，并调用唯一公开 AI 接口。
4. C 的 Pipeline 按“清洗→分句→BERT→余弦相似度→TextRank/PageRank→Token Budget→原文顺序恢复→Seq2Seq”生成 SummaryResult。
5. Worker 将 SummaryResult 或失败信息交给 SummaryService；SummaryService 成功持久化 summary、summary_time_ms、model_version 和 `completed`，失败持久化 summary_error 和 `failed`。
6. A/D 的 API 经 Service 返回新闻与用户状态；E 的客户端只按 API 契约显示。

## 4. 离线训练流与 B→C 模型交付

B 使用 CNewSum 处理 train/validation/test，验证候选模型后确定唯一正式 checkpoint，以 PyTorch 和 Hugging Face Transformers 微调，在完整正式摘要流程的 CNewSum test 上完成 ROUGE 与性能评价。B 向 C 交付：

```text
runtime/models/news_summarizer/
正式模型元信息：
model_name
model_version
tokenizer 信息
max_input_tokens
max_new_tokens
generation_config
```

B 的训练和 C 的在线推理必须使用同一 tokenizer、输入长度、生成长度、生成参数和 model_version。术语映射固定为：`max_source_length = max_input_tokens`、`max_target_length = max_new_tokens`；`SUMMARIZER_MAX_INPUT_TOKENS` 对应正式 `max_input_tokens`，`SUMMARIZER_MAX_NEW_TOKENS` 对应正式 `max_new_tokens`。阶段2由 B/C 统一现有配置和代码命名，不能由 C 自行缩短输入长度。

## 5. 在线 AI 推理与 C→D 接口

业务层公开契约固定且只能由 D 的 Worker 调用：

```python
class SummaryResult:
    summary: str
    generation_time_ms: int
    model_version: str

class SummaryPipeline:
    def load(self) -> None: ...
    def generate(self, article: str) -> SummaryResult: ...
```

`load()` 负责加载和预热正式组件。`generate()` 的计时从方法进入到最终摘要字符串生成完成；模型下载、首次加载、新闻请求、MySQL 查询及 HTTP 传输不计入。BERT 用于句子语义向量；TextRank 使用句间余弦相似度图进行关键句排序；Token Budget 按 `max_input_tokens` 选句，不固定 Top-N；Seq2Seq 仅负责最终生成。C 可替换内部实现，但未经接口变更流程不得修改该公共签名；D 不得绕过它调用 BERT、Tokenizer、TextRank 或 Transformer。

## 6. Crawler→NewsService 接口与清洗边界

```python
class RawArticle:
    title: str
    content: str
    category: str
    source: str
    source_url: str
    publish_time: datetime | None

class NewsSource:
    def fetch_articles(self) -> list[RawArticle]: ...
```

`source_a` 和 `source_b` 输出相同 RawArticle，NewsService 不依赖来源特例。D 的网页级清洗负责 HTML 标签、导航、广告、相关推荐、责任编辑、页面模板和非正文区域，输出真实正文字符串；C 的 NLP 级清洗负责控制字符、异常空白、字符规范化、中文分句、空/过短文本判断和超长模型输入处理。D 不实现中文分句，C 不理解网站 DOM。

## 7. A/D 数据库、用户状态与评价接口

A 维护 Schema、数据库公共连接约定、收藏、反馈、模型评价查询与接口协调。D 写新闻基本信息、新闻查询、摘要状态、Worker 和摘要结果。C 不直接操作业务数据库，B 不修改新闻业务表，E 不访问 MySQL。

新闻详情必须复用 A 的用户状态服务，冻结内部契约：

```python
UserService.get_news_user_state(db, client_id, news_id)
→ {is_favorite: bool, feedback: bool | None}
```

D 的详情逻辑不能重新实现 favorites/feedback 查询。B/C 向 A 的评价交付字段固定为 `model_name`、`model_version`、`dataset`、`dataset_split`、`sample_count`、`rouge1`、`rouge2`、`rougeL`、`avg_generation_time_ms`、`p95_generation_time_ms`；其中 dataset 固定 CNewSum、dataset_split 固定 test，model_version 与 SummaryResult 完全同源。B 负责主评价，C 配合完整 Pipeline 评价，A 负责 `model_evaluations` 规范和指标 API。

## 8. Worker 与摘要状态机

SummaryService 只负责摘要任务状态、事务、并发控制和数据库协调：查询当前状态；处理 API 摘要请求；completed 返回已有结果；processing 返回处理中；pending 保持待处理；failed 原子重置为 pending；协助 Worker 领取 pending 并完成 pending→processing；接收 Worker 成功结果或失败信息并持久化最终状态。SummaryService 不得持有或调用 SummaryPipeline，不得直接使用 BERT、TextRank 或 Transformer。

Worker 是唯一正式调用 `SummaryPipeline.generate(article)` 的业务组件。Worker 通过 SummaryService 原子领取 pending 新闻，状态变为 processing；Worker 调用 Pipeline 并将 SummaryResult 交回 SummaryService；发生异常时将错误信息交回 SummaryService。`POST /api/news/{news_id}/summary` 仅调用 SummaryService，不在 HTTP 线程运行 Transformer：completed 返回缓存，processing 返回处理中，pending 保持/确认 pending 后返回已接受，failed 置回 pending 后返回已接受重试。

```text
pending → processing → completed
                 └──→ failed → pending
```

SummaryService 依据 Worker 交付结果持久化：成功写 summary、summary_time_ms、model_version 和 completed；失败写 summary_error 和 failed。不得直接由 failed 变为 completed，也不得形成 API 与 Worker 两套摘要逻辑。

## 9. 参数命名、时间与接口变更

跨模块字段、API 字段、数据库字段和代码标识符均使用英文；文档、注释和 docstring 使用中文。客户端 API 时间为 ISO 8601 字符串，数据库时间为 DATETIME。分类固定为科技、财经、社会、体育、国内、国际。

任何成员认为接口不足时，必须依次：确认能否在模块内部解决；阅读本文件、API 与 DATABASE；提出字段/接口变更及影响角色；全员协商确认；先更新对应文档；最后修改代码。禁止为本模块运行而直接改动其他成员公共接口。
