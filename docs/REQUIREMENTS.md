# 终版需求基线

## 1. 项目目标

系统最终由 HarmonyOS 客户端、FastAPI 后端、MySQL、两个真实新闻来源、BERT、TextRank、Seq2Seq Transformer 和 CNewSum 构成。系统采集新闻、生成最终摘要、展示新闻和模型质量，并持久化收藏与反馈。

## 2. 功能需求

| 编号 | 需求名称 | 最终要求 | 负责人 | 阶段 | 模块/接口 | 验收标准 |
|---|---|---|---|---|---|---|
| FR-01 | 多新闻源采集 | 接入至少两个真实来源 | D | 3 | crawlers | 两来源均输出 RawArticle |
| FR-02 | 新闻正文提取 | 提取标题、正文、来源、URL、时间、分类 | D | 3 | Crawler→NewsService | 六字段完整或时间为空 |
| FR-03 | 网页噪声清理 | 去除 HTML、导航、广告、推荐等页面噪声 | D | 3 | crawlers | 入库 content 为正文 |
| FR-04 | 新闻分类映射 | 统一到科技、财经、社会、体育、国内、国际 | D | 3 | NewsService | 仅六类之一 |
| FR-05 | 新闻 SHA-256 去重 | 对正文计算 SHA-256 并阻止重复入库 | D | 3 | news_articles | content_hash 唯一 |
| FR-06 | 新闻 MySQL 持久化 | 保存采集信息和摘要状态 | D/A | 3 | NewsService/Schema | 字段符合 DATABASE |
| FR-07 | NLP 文本预处理 | 清洗、分句及异常文本检查 | C | 2 | clean_text/split_sentences | AI 单元测试通过 |
| FR-08 | BERT 句子语义表示 | 批量真实编码，单次加载，支持 GPU | C | 2 | BertEncoder | 句向量数量对应句子 |
| FR-09 | TextRank 关键句提取 | 用句间余弦图真实运行 TextRank/PageRank | C | 2 | TextRank | 输出同序重要性得分 |
| FR-10 | Token Budget 选择 | 按 max_input_tokens 选句并恢复原顺序 | C | 2 | SummaryPipeline | 不固定 Top-N |
| FR-11 | Seq2Seq 摘要生成 | 使用 B 的正式模型生成最终摘要 | B/C | 2 | SummaryPipeline | 真实模型输出 |
| FR-12 | 新闻分类展示 | 客户端固定展示六类 | E | 4 | GET /categories | 分类契约一致 |
| FR-13 | 新闻分页与刷新 | 支持 page、page_size、刷新 | D/E | 3/4 | GET /news | 正确分页，无 content |
| FR-14 | 新闻详情 | 展示新闻、状态和用户状态 | D/A/E | 3/4 | GET /news/{news_id} | 字段完整 |
| FR-15 | 新闻全文查看 | 客户端展示 content | E | 4 | 新闻详情 | 正文可阅读 |
| FR-16 | AI 摘要展示 | 展示摘要及处理状态 | D/E | 3/4 | 摘要/详情接口 | 不伪造摘要 |
| FR-17 | 收藏新闻 | X-Client-ID 下幂等收藏 | A/E | 3/4 | POST /favorites | 返回 is_favorite=true |
| FR-18 | 取消收藏 | X-Client-ID 下幂等取消 | A/E | 3/4 | DELETE /favorites | 返回 is_favorite=false |
| FR-19 | 收藏列表 | 查询客户端收藏新闻 | A/E | 3/4 | GET /favorites | 仅本客户端数据 |
| FR-20 | 用户摘要反馈 | 提交 helpful true/false | A/E | 3/4 | POST feedback | 返回当前评价 |
| FR-21 | 用户反馈持久化 | 同一 client/news 先插入后更新 | A | 3 | feedback | 唯一约束有效 |
| FR-22 | 模型质量评价 | 完整流水线在 CNewSum test 计算 ROUGE | B/C/A | 2/3 | model_evaluations | 三项真实指标入库 |
| FR-23 | 模型性能评价 | 记录平均与 P95 生成耗时 | B/C/A | 2/3 | model_evaluations | 计时规则合规 |
| FR-24 | HarmonyOS 模型指标展示 | 调用真实指标 API | A/E | 3/4 | GET /model/metrics | 不硬编码指标 |
| FR-25 | 摘要任务调度 | Worker 唯一调用在线 AI 并维护状态机 | D/C | 3 | Worker/SummaryPipeline | 状态迁移正确 |

## 3. 非功能需求

| 编号 | 要求 | 负责人 | 阶段 | 验收标准 |
|---|---|---|---|---|
| NFR-01 | Windows 10/11 x64 运行 | A | 6 | 在目标环境完成集成验证 |
| NFR-02 | 使用 MySQL 8.x | A | 1/6 | Schema 与数据库一致 |
| NFR-03 | 使用 HarmonyOS ArkTS/ArkUI | E | 4/6 | 客户端可完成全部流程 |
| NFR-04 | 使用 Hugging Face Transformers | B/C | 2 | 训练与在线加载可追溯 |
| NFR-05 | CNewSum 唯一正式数据集 | B | 2/6 | 训练/评价记录均为 CNewSum |
| NFR-06 | 正式总体质量 | B/C | 2/6 | CNewSum test 的完整正式 Pipeline `corpus_rougeL >= 0.40` |
| NFR-07 | 正式性能 | B/C | 2/6 | 模型已加载、GPU 已预热、batch_size=1 时，从 `SummaryPipeline.generate(article)` 进入至最终 summary 字符串完成的 `p95_generation_time_ms < 1500`；不含下载、首次加载、新闻抓取、HTTP、MySQL 查询 |
| NFR-08 | 后端不得在线训练 | B/C/D | 2/3 | 后端仅加载正式权重 |
| NFR-09 | 数据集、权重、缓存不提交 Git | A/B/C | 1/6 | Git 检查通过 |
| NFR-10 | 跨模块接口遵守冻结文档 | 全员 | 1-6 | 契约检查通过 |
| NFR-11 | 注释和 docstring 使用中文 | 全员 | 1-6 | 代码审查通过 |
| NFR-12 | API/数据库字段使用英文标识符 | 全员 | 1-6 | 文档与代码审查通过 |
| NFR-13 | 质量达标率 | B/C | 2/6 | `quality_pass_rate = CNewSum test 中单样本 ROUGE-L >= 0.40 的数量 / 实际评价样本数量 >= 0.95` |
| NFR-14 | 性能达标率 | B/C | 2/6 | `latency_pass_rate = 正式性能测试中 SummaryPipeline.generate(article) < 1500 ms 的数量 / 实际性能测试样本数量 >= 0.95` |
| NFR-15 | Test 隔离 | B/C | 2/6 | test 在最终正式评价前保持 held-out，不得参与候选选择或调参 |
| NFR-16 | 实验可追溯 | B | 2/6 | 训练、验证、评价和 failed/OOM/interrupted 均有真实运行记录 |
| NFR-17 | 模型来源可追溯 | B | 2/6 | 深入候选与正式模型具有公开来源、model card、许可证及 revision |
