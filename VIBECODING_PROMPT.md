# NewsSummarySystem Vibe Coding 统一约束 Prompt

## 1. 开始修改前先读取

AI 在修改仓库前必须先阅读：

1. `README.md`
2. `docs/REQUIREMENTS.md`
3. `docs/ARCHITECTURE.md`
4. 当前任务若涉及 REST，再读取 `docs/API.md`
5. 当前任务若涉及 MySQL，再读取 `docs/DATABASE.md`
6. 需要了解人员职责或现有任务划分时，再读取 `docs/DEVELOPMENT_PLAN.md`

文档职责：

- `REQUIREMENTS.md`：终版必须实现什么
- `ARCHITECTURE.md`：模块边界和跨模块接口
- `API.md`：前后端 REST 契约
- `DATABASE.md`：数据库字段、状态和读写职责
- `DEVELOPMENT_PLAN.md`：人员职责和建议任务划分
- `AI_PROMPTS.md`：AI 使用记录，不作为技术契约

如果文档与代码冲突，**以已冻结的需求和公共契约为依据，不得擅自重写公共接口来迁就当前实现**。先报告冲突和影响范围，再由用户决定如何处理。

---

## 2. 已冻结的项目底线

除非用户明确批准，不得改变：

- 客户端：HarmonyOS + ArkTS + ArkUI
- 后端：Python 3.11 + FastAPI
- 数据库：MySQL 8.x + SQLAlchemy + PyMySQL
- 正式数据集：**CNewSum**
- AI 框架：PyTorch + Hugging Face Transformers
- 在线摘要主流程：  
  `文本清洗 → 中文分句 → BERT → 余弦相似度 → TextRank/PageRank → Token Budget → 恢复原文顺序 → Seq2Seq Transformer → 最终摘要`
- 正式摘要通过 `SummaryPipeline` 对业务层提供
- Worker 是正式系统中唯一调用 `SummaryPipeline.generate(article)` 的业务组件
- 至少两个真实新闻来源
- 系统分类固定为：科技、财经、社会、体育、国内、国际
- 用户状态通过 `X-Client-ID`（UUID v4）区分
- 不实现账号密码和 JWT
- 终版包含新闻列表、详情、全文、摘要、收藏、反馈、模型指标
- 最终 ROUGE-L 目标不低于 0.40
- 预热后单篇摘要生成时间目标小于 1.5 秒

禁止擅自：

- 替换 CNewSum
- 删除 BERT、TextRank 或 Seq2Seq Transformer
- 用大模型 API 替代正式摘要模型
- 改变已冻结的 REST 路径、公共字段或数据库 Schema
- 引入 Redis、Kafka、Celery、Docker、Kubernetes、微服务、JWT 等未冻结技术
- 增加推荐、评论、登录等与课程目标无关的系统
- 为“工程化”目的增加不必要的复杂层级

---

## 3. 五人职责与文件边界

### A
负责：

- 项目架构和公共文档
- 数据库 Schema 和公共数据库规范
- FastAPI 公共规范
- 收藏、反馈、模型指标
- 公共接口协调和系统集成

A 可以主要修改：

- `docs/`
- `README.md`
- `backend/app/main.py`
- `backend/app/config.py`
- `backend/app/database.py`
- `backend/app/models.py`
- `backend/app/schemas.py`
- `backend/app/api/favorites.py`
- `backend/app/api/feedback.py`
- `backend/app/api/model.py`
- `backend/app/services/user_service.py`
- `backend/app/services/model_service.py`
- `sql/`
- `scripts/`

### B
负责：

- CNewSum
- Seq2Seq Transformer 训练
- 正式模型和 Tokenizer
- ROUGE
- Benchmark
- 模型交付

B 可以主要修改：

- `model_training/`
- `runtime/datasets/`
- `runtime/models/`

### C
负责：

- NLP 预处理
- BERT
- TextRank
- Token Budget
- 在线 Transformer
- `SummaryPipeline`
- AI 相关测试

C 可以主要修改：

- `backend/app/ai/`
- 与 AI 直接相关的测试文件

### D
负责：

- 真实新闻源
- 网页正文提取
- 网页级清洗
- 分类和去重
- 新闻业务
- Worker
- 新闻 API
- 摘要任务

D 可以主要修改：

- `backend/app/crawlers/`
- `backend/app/services/news_service.py`
- `backend/app/services/summary_service.py`
- `backend/app/api/news.py`
- `backend/app/worker.py`
- 与上述业务直接相关的测试文件

### E
负责：

- 完整 HarmonyOS 客户端
- Client ID
- 新闻列表、详情、全文
- 收藏、反馈、模型指标页面
- 客户端状态和网络处理

E 可以主要修改：

- `frontend_harmony/`

### 权限规则

每个人可以在自己职责范围内自主安排开发，不需要严格按照阶段或任务编号执行。

但是：

- 不得未经允许修改其他角色主要负责文件
- 不得为了本模块方便直接改变公共接口
- 不得复制实现本应由其他角色负责的业务
- 如果确实需要跨角色修改，先向用户说明原因、涉及文件和影响范围，再执行

---

## 4. 公共接口必须保持稳定

### B → C：正式模型交付

B 最终向 C 提供：

- `runtime/models/news_summarizer/`
- `runtime/models/news_summarizer/model_metadata.json`（唯一正式元信息 JSON）
- `model_name`
- `model_version`
- tokenizer 信息
- `max_input_tokens`
- `max_new_tokens`
- `generation_config`

C 必须读取并使用已确认的正式模型参数，不得自行猜测或私自改成另一套。`model_metadata.json` 至少包含 `model_name`、`model_version`、固定值 `dataset: CNewSum`、`tokenizer.name_or_path`、`max_input_tokens`、`max_new_tokens` 和 JSON 对象 `generation_config`；`model_version` 必须与 `SummaryResult.model_version` 相同，训练和在线 tokenizer 必须一致。具体值只能由真实实验填写。

B 的训练、验证、ROUGE、Benchmark 和候选选择记录固定存于 `runtime/training_runs/`，并以可追溯 run_id 保存真实参数、原因、结果和阻塞状态。正式候选必须先通过 `corpus_rougeL >= 0.40`、`quality_pass_rate >= 0.95`、`latency_pass_rate >= 0.95`、`p95_generation_time_ms < 1500` 四项硬门槛，才可按 `0.7 * quality_score + 0.3 * performance_score` 排序；完整定义见 `docs/ARCHITECTURE.md`。参数调优最多 10 轮（第 0 轮 baseline 不计入），不得伪造结果或以裸模型替代完整 Pipeline。

### C → D：AI 接口

业务层只依赖：

```python
SummaryPipeline.load() -> None
SummaryPipeline.generate(article: str) -> SummaryResult
```

`SummaryResult` 固定包含：

```text
summary
generation_time_ms
model_version
```

D 不得绕过 `SummaryPipeline` 直接使用 BERT、TextRank、Tokenizer 或 Transformer。

### D：Crawler → NewsService

统一使用：

```text
RawArticle:
    title
    content
    category
    source
    source_url
    publish_time
```

所有新闻来源必须输出同一结构。

D 负责网页级清洗；C 负责 NLP 级清洗。

### A → D：用户状态

新闻详情中的：

```text
is_favorite
feedback
```

必须复用 A 的用户业务逻辑，不允许 D 再实现一套收藏/反馈系统。

### A/D → E：REST

E 只按照 `docs/API.md` 开发。

不得：

- 根据 Python 源码自行猜 JSON
- 私自增加字段
- 私自改变路径
- 直接访问 MySQL
- 直接调用 Python AI

---

## 5. 修改公共契约的规则

以下内容属于公共契约：

- REST 路径
- API 请求/响应字段
- 数据库 Schema
- `RawArticle`
- `SummaryPipeline`
- `SummaryResult`
- B → C 模型交付字段
- 用户状态内部接口
- 摘要状态机

如认为公共契约需要修改：

1. 先说明当前问题
2. 说明为什么不能在当前模块内部解决
3. 列出受影响角色和文件
4. 给出建议修改方案
5. 等待用户确认
6. 先更新对应文档
7. 再修改实现

禁止为了“先跑起来”直接改契约。

---

## 6. 编码底线

- 文件名、类名、函数名、变量名、API 字段、数据库字段使用英文
- **所有代码注释使用中文**
- **所有 docstring 使用中文**
- **所有 TODO 使用中文**
- 不硬编码数据库密码、个人 IP、个人绝对路径
- 不提交 `.env`
- 不提交 CNewSum 原始数据
- 不提交模型权重、缓存和日志
- 不伪造新闻、摘要、ROUGE、性能指标或模型结果
- Mock 只能用于模块隔离测试，不能作为最终功能
- 优先只修改当前工作真正需要的文件
- 不顺手重构无关模块

TODO 建议格式：

```text
TODO(C)：说明待完成任务、输入、输出和依赖接口。
```

---

## 7. AI 的工作方式

用户可以直接指定：

- 当前角色
- 当前要做的功能
- 当前允许修改的文件
- 当前目标

不要求必须提供阶段或任务编号。

AI 应根据已有文档和角色边界自行完成职责范围内的工作。

开始修改前，只需简短确认：

```text
当前角色：
本次目标：
计划修改：
不会修改：
依赖的公共接口：
```

如果用户已经明确要求“直接执行”，完成上述内部核对后直接开始，不需要额外等待确认。

---

## 8. 遇到冲突时

如果发现：

- 文档和代码不一致
- 两个角色都在实现同一逻辑
- 当前接口无法满足需求
- 需要修改其他角色文件
- 需要改变公共字段

不要自行扩大修改范围。

先向用户报告：

```text
问题：
当前实现：
冻结契约：
影响角色：
建议方案：
```

等待用户决定。

---

## 9. 完成工作后的报告

完成后简要报告：

1. 修改了哪些文件
2. 完成了什么
3. 使用了哪些公共接口
4. 测试或验证结果
5. 是否留下 TODO
6. 是否发现跨模块问题
7. 是否修改公共接口
8. 是否修改其他角色负责文件

如果第 7 或第 8 项为“是”，必须说明是否得到用户授权。

如本次使用 AI 对项目产生实际修改，应将真实使用记录补充到 `docs/AI_PROMPTS.md`，或给出可由组员人工追加的记录内容。若原始 Prompt 超过 500 字，记录时必须概括为不超过 200 字的中文摘要；摘要须保留任务目标、关键约束、允许范围和禁止事项，不得伪造为原文或遗漏会影响执行边界的限制。

---

## 10. 核心原则

你是当前组员的开发辅助 AI，不是项目架构的重新设计者。

**组员可以自由决定自己职责内的开发顺序和实现节奏；AI 必须守住文件边界、公共接口、技术路线和真实性底线。**

先理解约束，再开发；  
只做职责范围内的事；  
接口稳定优先于个人实现便利；  
发现冲突先报告，不擅自改契约；  
最终结果必须真实、可测试、可交付。
