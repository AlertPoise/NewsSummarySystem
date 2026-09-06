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

B 只从 `runtime/datasets/` 读取 CNewSum；正式原始数据目录固定为 `runtime/datasets/CNewSum_v2/final/`。当前已发现 `dev.simple.label.jsonl`、`test.simple.anno.label.jsonl`、`test.simple.label.jsonl`、`test2017.simple.label.jsonl`、`test2018.simple.label.jsonl`、`train.simple.label.jsonl` 和 `LICENSE.md`，但其字段、编码及最终 train/validation/test 映射一律待 B2-01 根据真实格式和数据集说明验证，不得仅按文件名推定。数据集文件不得提交 Git。

唯一正式模型目录为 `runtime/models/news_summarizer/`。B 在真实实验确定唯一 checkpoint 后，必须在其中交付 Hugging Face 可直接加载的正式模型与 Tokenizer 文件，并且只能额外以 `runtime/models/news_summarizer/model_metadata.json` 作为 B→C 的统一模型元信息文件。本阶段只冻结契约，不创建虚假的模型、checkpoint 或元信息。

`model_metadata.json` 必须是 JSON 对象，至少符合以下结构；真实模型名、版本和参数仅可由真实实验填写：

```json
{
  "model_name": "...",
  "model_version": "...",
  "dataset": "CNewSum",
  "tokenizer": {
    "name_or_path": "..."
  },
  "max_input_tokens": 0,
  "max_new_tokens": 0,
  "generation_config": {}
}
```

`dataset` 固定为 `CNewSum`；`model_version` 必须与 `SummaryResult.model_version` 使用同一版本值；`generation_config` 必须为保存正式生成参数的 JSON 对象。C 的在线 Pipeline 必须读取并遵守该正式元信息，且不得自行改写 `max_input_tokens` 或 `max_new_tokens`。B 的训练 tokenizer 和 C 的在线 tokenizer 必须一致。术语映射固定为：`max_source_length = max_input_tokens`、`max_target_length = max_new_tokens`；`SUMMARIZER_MAX_INPUT_TOKENS` 对应正式 `max_input_tokens`，`SUMMARIZER_MAX_NEW_TOKENS` 对应正式 `max_new_tokens`。阶段2由 B/C 统一现有配置和代码命名，不能由 C 自行缩短输入长度。

### B 实验记录、验收与依赖边界

`runtime/training_runs/` 是 B 唯一正式实验运行记录目录。每个真实实验须使用可追溯、稳定的 `run_id` 子目录，并在其中保存 JSON 或 JSONL 运行记录；禁止使用 `final`、`final2`、`best_new`、`final_final` 等不可维护名称。每条运行记录至少包含 `run_id`、`timestamp`、`task`、`candidate_model`、`model_version`、`dataset`、`dataset_split`、`training_parameters`、`generation_parameters`、`sample_count`、`rouge1`、`rouge2`、`rougeL`、`quality_pass_rate`、`avg_generation_time_ms`、`p95_generation_time_ms`、`latency_pass_rate`、`status` 和 `notes`；某轮未进行的真实评价字段可缺省或为 null，禁止填写虚假结果。checkpoint、中间日志、生成结果和其他运行产物也只能保存在该运行目录或 `runtime/` 的正式模型目录，默认不得提交 Git。

正式质量指标为完整正式 Pipeline 在 CNewSum test 上的 `corpus_rougeL >= 0.40`。`quality_pass_rate` 定义为 CNewSum test 中“单样本 ROUGE-L >= 0.40”的样本数除以实际评价样本数，必须 `>= 0.95`。正式性能测试在 Pipeline 已 load、GPU 已预热、batch_size=1 时，从 `SummaryPipeline.generate(article)` 方法进入至最终 summary 字符串完成计时；不包括模型下载、首次模型加载、新闻网络抓取、HTTP 或 MySQL 查询。`latency_pass_rate` 定义为生成时间 `< 1500 ms` 的性能测试样本数除以实际性能测试样本数，必须 `>= 0.95`；同时 `p95_generation_time_ms < 1500`。不得跳过 BERT、TextRank 或 Transformer，不得改为固定 Top-N 或裸 Seq2Seq benchmark。

候选先通过全部硬门槛（`corpus_rougeL >= 0.40`、`quality_pass_rate >= 0.95`、`latency_pass_rate >= 0.95`、`p95_generation_time_ms < 1500`）才能排序。合格候选采用 `quality_score = clamp((corpus_rougeL - 0.40) / (1.00 - 0.40), 0, 1)`、`performance_score = clamp((1500 - p95_generation_time_ms) / 1500, 0, 1)`、`final_selection_score = 0.7 * quality_score + 0.3 * performance_score`，其中 `clamp(x, 0, 1)` 将数值限制在 `[0, 1]`。同分时依次选择更高 `corpus_rougeL`、更低 `p95_generation_time_ms`、更小或更稳定的模型；加权分数绝不能掩盖硬门槛失败。

B 的参数调优最多 10 轮；第 0 轮可作为 baseline/candidate baseline，不计入这 10 轮。每一轮必须基于上一轮真实结果，修改有明确依据的一组训练或生成参数，完成该轮所需训练或评价，并记录参数变化、原因和真实结果；参数完全不变不得伪造为新轮次。若在第 10 轮前已满足全部硬门槛且继续调参收益极低，可提前结束。第 10 轮后仍不合格时，必须保存最佳真实结果、标记“未通过最终验收”并输出瓶颈分析，不得降低阈值或伪造成功，也不得改变数据集、BERT/TextRank 存在性或 SummaryPipeline 公共接口来制造成功。

B 可独立完成 B2-01～B2-09、B2-12；B2-10 必须等待 C2-13 的完整正式 Pipeline 输出，B2-11 必须等待 C2-11 的 `SummaryPipeline.generate()`，B2-14 必须等待 C2-14 性能优化完成。C 尚未完成时，B 必须保存当前检查点和 `blocked_by`，继续不依赖 C 的工作；无独立工作时停在明确检查点，禁止用裸 Transformer 或裸 `model.generate()` 冒充最终结果。B 可以仅在 `model_training/` 范围按真实代码需要维护离线训练依赖（推荐 `model_training/requirements.txt`）；不得污染或重构 backend 依赖，不得预先添加无实际代码需要的包，也不得引入 Docker、Conda 或复杂环境管理框架。

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

## 9. B 阶段实验协议冻结

核心 CNewSum split 为 train 275,596、dev 14,356、test 14,355（304,307）；test.anno、test2017、test2018 的重叠/来源待 B2-01 真实核验。普通样本基线字段为 article（句子数组）、summary（Seq2Seq target）、id、label；label 语义待官方资料确认，anno 的 adequacy/deducibility 不是训练 target，标准化必须保留句边界和字段来源。

从模型决策开始只允许 train/dev：train 用于训练，dev 用于 validation、选择、调参与错误分析；所有 test 文件保持 held-out，首次正式 test 在 B2-10 且等待 C2-13。test ROUGE、loss、生成、长度或错误模式指导修改均为 test leakage。

唯一评价协议为 `cnewsum_mlrouge_compatible_v1`。依据 [CNewSum 官方项目](https://dqwang122.github.io/projects/CNewSum/)：中文按字符切分，英文词与数字按空格切分后映射；项目记录使用 [0,1]。空格规范化、大小写和标点的 MLROUGE parity 细节待 evaluator 实现验证，不得猜测。corpus_rougeL 是该统一 evaluator 对完整 split 的 ROUGE-L F；quality_pass_rate 是同规范下单样本 ROUGE-L F≥0.40 的比例。

最多 3 个深入下载/pilot 候选，模型必须公开、可加载、有 model card、许可证及 model/tokenizer revision。B 新增训练/模型运行产物预算 10GB；可清理冗余 checkpoint/optimizer，但保留元数据、日志、指标、失败原因、最佳 checkpoint/最终模型并记录清理。正式训练必须 CUDA；无 CUDA 标记 blocked，可合法 OOM 调整但不得缩减 train、使用 test 或降低阈值。每个真实运行都在 training_runs 留 parent_run_id、时间、来源/revision、数据指纹、参数、硬件、loss/ROUGE、status/error、原因和 artifacts；未运行指标为 null。

## 10. 参数命名、时间与接口变更

跨模块字段、API 字段、数据库字段和代码标识符均使用英文；文档、注释和 docstring 使用中文。客户端 API 时间为 ISO 8601 字符串，数据库时间为 DATETIME。分类固定为科技、财经、社会、体育、国内、国际。

任何成员认为接口不足时，必须依次：确认能否在模块内部解决；阅读本文件、API 与 DATABASE；提出字段/接口变更及影响角色；全员协商确认；先更新对应文档；最后修改代码。禁止为本模块运行而直接改动其他成员公共接口。
