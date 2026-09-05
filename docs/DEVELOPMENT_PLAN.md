# 六阶段开发计划、任务台账与验收

## 1. 任务模板与通用边界

每行任务均按以下统一模板填写：**任务编号、负责人、阶段、任务名称/目标、允许修改、禁止修改、输入、输出、依赖任务/接口、交付给、实现要求、完成标准、测试/验收、禁止事项**。表内“输入→输出”“依赖/交付”“验收”分别覆盖模板的输入、输出、依赖、交付、实现要求、完成标准和测试字段；未单列的禁止事项适用本节通用规则。

| 角色 | 允许修改范围 | 禁止修改范围 | 通用禁止事项 |
|---|---|---|---|
| A | docs、数据库公共层、API 公共层、用户/模型服务、sql、scripts | AI、Crawler、HarmonyOS、训练实现 | 绕过 Service、硬编码密码 |
| B | model_training、runtime/datasets、runtime/models | C 的在线 AI、Crawler、业务 API、HarmonyOS | 使用非 CNewSum、在线训练 |
| C | backend/app/ai、AI 测试 | Schema、Crawler、业务 Service、HarmonyOS | 改动 Pipeline 公共接口、直写业务表 |
| D | crawlers、新闻/摘要 Service、news API、worker | Schema、用户服务、训练、HarmonyOS | 虚构新闻、绕过 Pipeline |
| E | frontend_harmony | Python、SQL、MySQL、训练 | 直连 MySQL/Python AI、硬编码指标 |

所有 API、Schema、数据库与公共接口变更均遵循 ARCHITECTURE 的接口变更流程。所有代码注释/docstring 使用中文，字段和标识符使用英文。

## 2. 阶段1：需求、架构、职责、接口冻结

| 任务编号 | 负责人 | 任务名称/目标 | 允许修改 | 输入→输出 | 依赖/交付 | 实现要求与验收 |
|---|---|---|---|---|---|---|
| A1-01 | A | 项目文档和架构维护 | README、docs | 课程需求→冻结文档 | 无→全员 | 需求、架构、职责、接口完整；文档审查无死链 |
| A1-02 | A | MySQL Schema维护 | DATABASE、models、DDL 规范 | 业务字段→四表字段定义 | FR-06/21/22→D/B/C | 字段、约束、读写职责明确；文档与 ORM/DDL 对照 |
| A1-03 | A | API公共规范 | API、schemas 规范 | 功能需求→统一 REST 契约 | FR-12至24→D/E | 路径、JSON、错误码、并发语义完整；契约审查 |
| A1-04 | A | FastAPI公共层规范 | ARCHITECTURE、main/config 规范 | 依赖规则→Route/Service 边界 | A1-03→D | API 不直连 AI/业务数据库；边界审查 |

**阶段1验收：**需求完整、架构完整、数据库完整、API 完整、五人任务明确、跨模块接口明确；不实现阶段2及以后的功能。

## 3. 阶段2：CNewSum、正式模型与在线 AI

### B 任务

| 任务编号 | 负责人 | 任务名称/目标 | 允许修改 | 输入→输出 | 依赖/交付 | 实现要求与验收 |
|---|---|---|---|---|---|---|
| B2-01 | B | CNewSum原始数据检查 | model_training、datasets | `runtime/datasets/CNewSum_v2/final/` 原始 CNewSum→检查报告 | 无→B2-02 | 确认字段、编码、数据集说明和划分；仅 CNewSum；不得仅按文件名推定 train/validation/test |
| B2-02 | B | CNewSum标准化 | model_training、datasets | 原始数据→id/article/summary | B2-01→B2-03/C | 可复现转换；样本字段完整 |
| B2-03 | B | CNewSum统计分析 | model_training | 标准样本→长度/数量统计 | B2-02→B2-06 | 统计可支撑长度参数选择 |
| B2-04 | B | 正式Seq2Seq模型候选验证 | model_training | 训练集/验证集→候选结果 | B2-02→B2-05 | 只记录真实实验，不伪造结果 |
| B2-05 | B | 最终checkpoint和Tokenizer确定 | model_training、models | 候选结果→唯一模型/Tokenizer | B2-04→B2-12/C | 训练与在线 tokenizer 一致 |
| B2-06 | B | 训练参数确定 | config、training | 统计/验证→正式参数 | B2-03/05→B2-07/C | 映射 max_input_tokens/max_new_tokens |
| B2-07 | B | Transformer微调 | training、models | CNewSum/参数→正式权重 | B2-05/06→B2-08 | PyTorch+Transformers，离线训练 |
| B2-08 | B | 验证集评价 | evaluate | 权重/validation→验证指标 | B2-07→B2-09 | 使用真实生成结果 |
| B2-09 | B | 正式模型导出 | models | 验收模型→news_summarizer | B2-08→B2-12/C | 目录可由 C 只读加载；交付 Hugging Face 可加载模型与 Tokenizer，不创建假产物 |
| B2-10 | B | CNewSum test ROUGE评价 | evaluate | 完整流程/test→三项 ROUGE、corpus_rougeL、quality_pass_rate | B2-09/C2-13→B2-13/A | 必须等 C2-13 的完整正式 Pipeline；`corpus_rougeL>=0.40`、`quality_pass_rate>=0.95`；非裸模型结果 |
| B2-11 | B | 初始性能 Benchmark | benchmark | B2-09 正式模型与已预热完整 Pipeline→初始 avg_generation_time_ms、p95_generation_time_ms、latency_pass_rate、性能瓶颈 | B2-09/C2-11→C2-14 | 必须等 C2-11；batch_size=1；从 generate 进入至最终摘要结束计时；不依赖 C2-14 |
| B2-12 | B | 正式模型信息交付C | models、元信息 | 权重/配置→模型交付包 | B2-09→C2-09 | `runtime/models/news_summarizer/model_metadata.json` 是唯一正式元信息；含名称、版本、CNewSum、tokenizer、长度、generation_config |
| B2-13 | B | 模型评价结果交付A | 评价产物 | 最终 ROUGE 与最终性能结果→固定字段记录 | B2-10/B2-14→A3-06 | dataset=CNewSum、split=test，字段全量一致，不使用初始 Benchmark |
| B2-14 | B | 最终性能 Benchmark | benchmark | C2-14 优化后的正式 Pipeline→最终 avg_generation_time_ms、p95_generation_time_ms、latency_pass_rate、正式性能验收结果 | B2-11/C2-14→B2-13/A | 必须等 C2-14；batch_size=1、模型已加载、GPU 已预热；`latency_pass_rate>=0.95`、`p95_generation_time_ms<1500` |

### B 自动实验、选择与阻塞规则

所有 B 的真实训练、验证、ROUGE、Benchmark 和候选选择运行都必须记录到唯一目录 `runtime/training_runs/`；每个运行使用可追溯的 `run_id` 子目录及 JSON/JSONL 记录，字段和 Git 忽略规则以 `ARCHITECTURE.md` 为准。不得写入不存在的结果，不得使用 `final`、`final2`、`best_new` 或 `final_final` 等名称。

最终候选先同时满足硬门槛：`corpus_rougeL >= 0.40`、`quality_pass_rate >= 0.95`、`latency_pass_rate >= 0.95`、`p95_generation_time_ms < 1500`。仅在此后按照 `quality_score = clamp((corpus_rougeL - 0.40) / 0.60, 0, 1)`、`performance_score = clamp((1500 - p95_generation_time_ms) / 1500, 0, 1)`、`final_selection_score = 0.7 * quality_score + 0.3 * performance_score` 排序；`clamp` 将数值限制在 `[0,1]`。同分时依次取更高 corpus_rougeL、更低 P95、再取更小或更稳定模型。无合格候选时不得以加权分数或降低验收线伪造正式模型。

第 0 轮 baseline 不计入调参上限。此后每一轮必须根据上一轮真实结果，有依据地改变一组训练或生成参数、完成所需训练或评价并记录变化、原因和结果；参数完全不变不得形成新轮次。最多 10 轮；提前满足全部硬门槛且继续调参收益极低时可结束。第 10 轮仍失败时，保存最佳真实结果，标记“未通过最终验收”并输出瓶颈分析，不得继续无限搜索或伪造成功。

B2-10、B2-11、B2-14 到达依赖点但 C 未完成时，B 保存当前检查点并在实验记录写入 `blocked_by`，继续可独立完成的 B 工作；没有独立任务时停在明确检查点。不得用裸 Transformer 或 `model.generate()` 冒充完整 Pipeline 的最终 ROUGE 或性能。B 可按实际代码需要在 `model_training/` 增加最小离线依赖文件；不得污染 backend、预装无需求包、引入 Docker/Conda 或复杂环境管理。

### C 任务

| 任务编号 | 负责人 | 任务名称/目标 | 允许修改 | 输入→输出 | 依赖/交付 | 实现要求与验收 |
|---|---|---|---|---|---|---|
| C2-01 | C | NLP文本规范化 | app/ai | article→清洗文本 | 无→C2-02 | 处理控制字符、空白、异常字符 |
| C2-02 | C | 中文分句 | app/ai | 清洗文本→有序句子 | C2-01→C2-04 | 处理空、过短、超长文本 |
| C2-03 | C | BERT checkpoint 选择与模型加载 | app/ai | CNewSum/新闻语言特点、可用中文 BERT checkpoint、本机硬件、AI 配置→正式 BERT checkpoint、Tokenizer/Encoder、可复用 BertEncoder | C2-01/C2-02→C2-04；无外部角色依赖 | C 自行验证选择；使用 Hugging Face、单次加载、GPU、inference_mode/no_grad、批量句编码；写入对应配置，不改变 B 的 Seq2Seq 交付 |
| C2-04 | C | BERT批量句编码 | app/ai | 句子→句向量 | C2-02/03→C2-05 | 向量数与句数对应 |
| C2-05 | C | 句子余弦相似度 | app/ai | 句向量→相似度图 | C2-04→C2-06 | 相似度计算可测试 |
| C2-06 | C | TextRank/PageRank | app/ai | 相似度图→句子得分 | C2-05→C2-07 | 真实 PageRank，非固定 Top-N |
| C2-07 | C | Token Budget | app/ai | 得分/句子/长度→选句索引 | C2-06/B2-12→C2-08 | 不超 max_input_tokens |
| C2-08 | C | 关键句原文顺序恢复 | app/ai | 选句索引→有序输入文本 | C2-07→C2-11 | 按原始位置恢复 |
| C2-09 | C | B正式Transformer在线加载 | app/ai | B交付包→加载模型 | B2-12→C2-10 | 只读正式目录，参数一致 |
| C2-10 | C | SummaryPipeline.load | app/ai | 配置/组件→预热 Pipeline | C2-03/09→C2-11 | 不改变冻结签名 |
| C2-11 | C | SummaryPipeline.generate | app/ai | article→SummaryResult | C2-01至10→D3-12 | 全链路计时，字段固定 |
| C2-12 | C | AI异常处理 | app/ai/tests | 非法文本/模型异常→可处理失败 | C2-11→D3-12 | 不伪造摘要，异常可定位 |
| C2-13 | C | 完整Pipeline评价配合 | app/ai | test 样本→真实最终摘要 | C2-11→B2-10 | 评价覆盖完整路径 |
| C2-14 | C | Pipeline性能优化 | app/ai | 初始 Benchmark 与性能瓶颈→优化后的完整 SummaryPipeline | B2-11→B2-14 | 不绕过 BERT/TextRank，不改变冻结接口或删除正式步骤；若改变摘要结果、关键句选择或 generation 参数，必须重新执行 B2-10 并保持 ROUGE-L≥0.40 |

**阶段2验收：**真实 CNewSum、唯一正式 Seq2Seq、真实 BERT/TextRank、可加载 SummaryPipeline、完整 Pipeline ROUGE-L≥0.40、预热后单篇<1.5秒，指标可交付 A。

## 4. 阶段3：新闻、Worker、后端业务 API

### A 任务

| 任务编号 | 负责人 | 任务名称/目标 | 允许修改 | 输入→输出 | 依赖/交付 | 实现要求与验收 |
|---|---|---|---|---|---|---|
| A3-01 | A | 收藏业务 | 用户服务/API | client_id/news_id→收藏状态 | API→E | POST 幂等，返回固定 JSON |
| A3-02 | A | 取消收藏业务 | 用户服务/API | client_id/news_id→非收藏状态 | A3-01→E | DELETE 幂等成功 |
| A3-03 | A | 收藏列表业务 | 用户服务/API | client_id→新闻列表 | A3-01→E | 仅返回该客户端收藏 |
| A3-04 | A | 用户摘要反馈 | 用户服务/API | client_id/news_id/helpful→评价 | API→E | 首次 INSERT，之后 UPDATE |
| A3-05 | A | 用户状态查询 | 用户服务 | db/client_id/news_id→状态对象 | A3-01/04→D3-14 | 复用唯一内部契约 |
| A3-06 | A | 模型指标查询 | 模型服务/API | 最新评价→指标响应 | B2-13→E | CNewSum/test 固定字段 |
| A3-07 | A | 与D新闻详情集成协调 | 服务/API | 新闻详情+用户状态→详情响应 | A3-05/D3-10→D/E | D 不复制用户查询 |

### D 任务

| 任务编号 | 负责人 | 任务名称/目标 | 允许修改 | 输入→输出 | 依赖/交付 | 实现要求与验收 |
|---|---|---|---|---|---|---|
| D3-01 | D | 第一个真实新闻来源 | crawlers | 来源A→RawArticle | base→D3-07 | 不虚构新闻 |
| D3-02 | D | 第二个真实新闻来源 | crawlers | 来源B→RawArticle | base→D3-07 | 字段结构相同 |
| D3-03 | D | 网页正文提取 | crawlers | 页面→标题/正文/元数据 | D3-01/02→D3-04 | 提取真实正文 |
| D3-04 | D | 网页级清洗 | crawlers | 页面正文→去噪正文 | D3-03→D3-07 | 清除 DOM 噪声，不写 NLP 分句 |
| D3-05 | D | 分类映射 | NewsService | 来源分类→六类 | D3-03→D3-07 | 严格六分类 |
| D3-06 | D | SHA-256去重 | NewsService | content→content_hash/去重结果 | D3-04→D3-07 | 依赖唯一约束 |
| D3-07 | D | 新闻入库 | NewsService | RawArticle→NewsArticle pending | D3-04至06→D3-08 | 写入职责字段 |
| D3-08 | D | 分类查询业务 | NewsService/news API | 无→固定六分类 | API→E | 不按数据库动态返回 |
| D3-09 | D | 新闻分页查询 | NewsService/news API | page/category→列表页 | D3-07→E | 默认时间倒序，无 content |
| D3-10 | D | 新闻详情查询 | NewsService/news API | news_id→新闻详情 | D3-07/A3-05→D3-14 | 详情字段完整 |
| D3-11 | D | SummaryService | 摘要服务 | news_id、新闻记录、当前 summary_status、Worker 传回的 SummaryResult 或错误信息→摘要任务状态、任务领取结果、持久化状态结果 | DATABASE 状态机/API 摘要语义→D3-12/D3-13 | 只处理状态、事务、并发控制和持久化；不得依赖 C2-11、不得持有或调用 SummaryPipeline |
| D3-12 | D | Worker | worker | SummaryService 提供的 pending/processing 新闻、C 的 SummaryPipeline→SummaryResult 或失败信息 | D3-11/C2-11→D3-13/E | 唯一正式调用 SummaryPipeline.generate(article)；生成结束后将结果或失败信息交给 SummaryService 持久化 |
| D3-13 | D | 摘要触发和重试业务 | news API/service | news_id/status→202或200 | D3-11→E | 只调用 SummaryService；HTTP 线程不调用 Worker 内部 AI 或 SummaryPipeline |
| D3-14 | D | 与A用户状态集成 | NewsService | user state→详情字段 | A3-05→A3-07/E | 不重写收藏/反馈查询 |

**阶段3验收：**至少两个真实新闻源、正文提取、去噪、分类、去重、MySQL、Worker、新闻 API、收藏、反馈和模型指标全部满足 API/DATABASE 契约。

## 5. 阶段4：HarmonyOS 客户端

| 任务编号 | 负责人 | 任务名称/目标 | 允许修改 | 输入→输出 | 依赖/交付 | 实现要求与验收 |
|---|---|---|---|---|---|---|
| E4-01 | E | DevEco正式工程 | frontend_harmony | 文档→工程骨架 | 无→E4-02 | ArkTS/ArkUI 正式工程 |
| E4-02 | E | HttpClient/API客户端 | frontend_harmony | API.md→统一请求层 | E4-01→各页面 | 不读 Python 源码实现 |
| E4-03 | E | Client ID | frontend_harmony | UUID→Preferences/client_id | E4-02→用户 API | UUID v4、持久化、header 合规 |
| E4-04 | E | News数据Model | frontend_harmony | API JSON→ArkTS model | E4-02→页面 | 字段名与 API 一致 |
| E4-05 | E | MainPage框架 | frontend_harmony | 页面需求→导航框架 | E4-01→各视图 | 首页/收藏/关于入口 |
| E4-06 | E | 新闻分类 | frontend_harmony | GET categories→六类 UI | E4-02→E4-07 | 不硬编码额外分类 |
| E4-07 | E | 新闻列表 | frontend_harmony | GET news→卡片列表 | E4-04/06→E4-08 | 不显示 content |
| E4-08 | E | 分页加载 | frontend_harmony | 页码→追加列表 | E4-07→验收 | 遵守 1~50 约束 |
| E4-09 | E | 刷新 | frontend_harmony | 刷新动作→首屏重载 | E4-07→验收 | 状态正确复位 |
| E4-10 | E | 新闻详情 | frontend_harmony | GET detail→详情页 | E4-03/04→E4-11 | 正确处理可选 client id |
| E4-11 | E | AI摘要展示 | frontend_harmony | summary/status→摘要组件 | E4-10→验收 | 不伪造处理结果 |
| E4-12 | E | 新闻全文 | frontend_harmony | content→全文 UI | E4-10→验收 | 可读显示正文 |
| E4-13 | E | 收藏操作 | frontend_harmony | favorites API→状态切换 | E4-03/02→E4-14 | 遵守幂等语义 |
| E4-14 | E | 收藏列表 | frontend_harmony | GET favorites→列表 | E4-13→验收 | client id 必填 |
| E4-15 | E | 摘要反馈 | frontend_harmony | feedback API→当前评价 | E4-03/10→验收 | 可重复更新 |
| E4-16 | E | 模型指标页面 | frontend_harmony | GET metrics→指标 UI | E4-02→验收 | 真实 API 数据 |
| E4-17 | E | Loading状态 | frontend_harmony | 请求中→加载 UI | 各请求→验收 | 页面可见且可恢复 |
| E4-18 | E | Empty状态 | frontend_harmony | 空响应→空 UI | 各列表→验收 | 不与错误混淆 |
| E4-19 | E | Error/网络异常状态 | frontend_harmony | HTTP/网络错误→错误 UI | 各请求→验收 | 显示可理解信息 |

**阶段4验收：**完整客户端支持分类、列表、分页、刷新、详情、摘要、全文、收藏、反馈、指标及 Loading/Empty/Error 状态，所有数据经 API。

## 6. 阶段5：端到端联调

| 任务编号 | 负责人 | 任务名称/目标 | 允许修改 | 输入→输出 | 依赖/交付 | 实现要求与验收 |
|---|---|---|---|---|---|---|
| A5-01 | A | 总体端到端集成 | 集成相关模块 | 全链路→联调记录 | 阶段2-4→全员 | 网站→Crawler→MySQL→Worker→AI→API→HarmonyOS 真实跑通 |
| A5-02 | A | REST契约一致性检查 | docs/API、A/D/E 边界 | 实现/文档→差异清单 | 阶段3/4→全员 | 路径、字段、状态码一致 |
| A5-03 | A | 数据库一致性检查 | DATABASE、Schema 边界 | ORM/DDL/业务→检查结果 | 阶段3→全员 | 字段、约束、状态机一致 |
| A5-04 | A | 五模块联调问题协调 | 跨模块文档与修复协调 | 缺陷→责任/修复记录 | A5-01至03→全员 | 所有 Mock 删除 |

**阶段5验收：**真实网站至 HarmonyOS 的全链路运行，收藏、反馈和模型评价同时可用，无 Mock 或双重摘要逻辑。

## 7. 阶段6：测试、优化与提交

| 任务编号 | 负责人 | 任务名称/目标 | 允许修改 | 输入→输出 | 依赖/交付 | 实现要求与验收 |
|---|---|---|---|---|---|---|
| A6-01 | A | 系统集成测试 | 测试/文档 | 联调系统→集成报告 | A5-01→全员 | Windows、数据库、API 全量验证 |
| A6-02 | A | README最终整理 | README/docs | 真实结果→最终入口文档 | A6-01→提交 | 不声明未完成能力 |
| A6-03 | A | 软件实践文档汇总 | docs | 各角色材料→实践文档 | B/C/D/E→提交 | 证据可追溯 |
| A6-04 | A | 最终提交检查 | 全仓库检查 | 成果→提交清单 | A6-01至03→全员 | 不含数据、权重、缓存、密码 |
| B6-01 | B | 最终 CNewSum test ROUGE 复核 | model_training、评价材料 | 最终正式模型、最终 SummaryPipeline、CNewSum test→最终 ROUGE-1、ROUGE-2、ROUGE-L | B2-10/C2-13/阶段5最终版本→A6-03/A6-04 | 使用完整 Pipeline，不得以裸 Transformer 冒充；ROUGE-L≥0.40 |
| B6-02 | B | 最终性能 Benchmark 复核 | model_training、评价材料 | 最终联调正式 Pipeline→最终 avg_generation_time_ms、p95_generation_time_ms、正式性能记录 | B2-14/C2-14/阶段5最终版本→A6-03/A6-04 | 沿用冻结计时规则，batch_size=1，模型已加载且 GPU 已预热 |
| B6-03 | B | 模型训练与评价材料整理 | model_training、docs | CNewSum处理记录、模型选择、训练配置、最终模型信息、B6-01/B6-02→训练和评价材料 | B6-01/B6-02→A6-03 | 数据说明、处理、模型依据、参数、训练、版本、ROUGE、性能和验收结论均来自真实实验 |
| C6-01 | C | AI单元和异常测试 | AI/tests | AI 样本→测试结果 | C2→A6-01 | 覆盖清洗、BERT、TextRank、Pipeline 异常 |
| C6-02 | C | AI实现章节文档整理 | docs | 实测过程→AI说明 | C6-01→A6-03 | 与正式实现一致 |
| D6-01 | D | Crawler测试 | crawlers/tests | 两来源→测试报告 | D3→A6-01 | 提取、去噪、映射、去重均覆盖 |
| D6-02 | D | 新闻业务和Worker测试 | services/API/worker tests | 新闻任务→测试报告 | D3→A6-01 | 状态机、并发、持久化覆盖 |
| E6-01 | E | HarmonyOS完整功能测试 | frontend_harmony | 客户端→测试记录 | E4/A5→A6-01 | 全功能和异常状态覆盖 |
| E6-02 | E | 页面截图和演示流程 | frontend_harmony/docs | 真实页面→截图/流程 | E6-01→A6-03 | 截图对应真实接口 |
| E6-03 | E | 演示视频 | frontend_harmony/docs | 真实系统→视频 | E6-02→提交 | 展示端到端与核心功能 |

**阶段6验收：**B 负责最终模型质量、性能复核和训练/评价材料；全员完成模块与集成测试、ROUGE/性能复核、实践文档、AI 提示词、演示视频和最终提交检查。
