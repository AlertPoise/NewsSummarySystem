# AI 使用记录

## 统一记录模板

```text
日期：
人员：
角色：
阶段：
任务编号：
使用工具：
任务目的：
完整Prompt：
Prompt 类型：完整原文 / Prompt 概括
会话/任务标识：
涉及文件：
AI 是否实际修改文件：true / false
AI生成内容：
自动执行范围：
人工检查：
人工修改：
人工确认项：
Git commit：pending / commit hash
最终结果：
AI_PROMPTS_PENDING：false

```

每次使用 AI 协助修改项目时，责任人须在同一工作周期内按模板追加记录；记录必须列出真实涉及文件与人工检查结果。

AI 修改任何仓库文件时必须同周期直接追加本文件；纯阅读、解释或只读检查无需记录。历史记录只追加，人工检查/修改/commit 未发生时填写 pending，禁止伪造。无法写入时使用 `AI_PROMPTS_PENDING=true`，任务不得称完全完成。/goal 必须持续记录重要修改节点；实验参数与结果仍放在 runtime/training_runs。

若原始 Prompt 超过 500 字，`完整Prompt` 字段改为不超过 200 字的中文概括，并明确标注为“Prompt 概括”；概括必须覆盖任务目标、关键约束、允许范围和禁止事项，不得伪称原文。

## 初始化记录

日期：2026-09-04

人员：A

角色：项目架构与文档维护

阶段：阶段1

任务编号：A1-01

使用工具：Codex

任务目的：初始化《基于自然语言处理的新闻文章自动摘要系统设计与实现》的工程目录、文档、数据库和代码骨架。

完整Prompt：当前未保存第一次 Codex 初始化使用的完整 Prompt 原文。

涉及文件：README、docs、backend、model_training、frontend_harmony、sql、scripts、runtime。

AI生成内容：阶段1目录、初始中文文档、数据库 DDL、FastAPI 健康检查及后续模块骨架。

人工检查：目录、接口、数据库、TODO 格式、注释语言、密码占位符和伪造结果。

人工修改：待 A 记录。

最终结果：形成初始阶段1工程方案。

TODO(A-阶段1)：由A补充第一次Codex初始化使用的完整Prompt原文；输入为可追溯的首次会话记录，输出为本条“完整Prompt”的完整原文，必须遵守本文件统一记录模板。

## 本次文档维护记录

日期：2026-09-04

人员：A

角色：项目架构与文档维护

阶段：阶段1

任务编号：A1-01、A1-02、A1-03、A1-04

使用工具：Codex

任务目的：精简文档数量、固化跨模块接口、任务台账、REST 契约和字段职责。

完整Prompt：本次会话中用户粘贴的“你现在正在维护课程项目仓库：NewsSummarySystem”完整要求文本。

涉及文件：README.md、docs/REQUIREMENTS.md、docs/ARCHITECTURE.md、docs/DEVELOPMENT_PLAN.md、docs/API.md、docs/DATABASE.md、docs/AI_PROMPTS.md。

AI生成内容：重组现有 Markdown，删除已被吸收的三份文档，并记录文档与现有代码差异。

人工检查：文档数量、接口一致性、死链接、非 Markdown 修改和代码差异清单。

人工修改：待 A 验收补充。

最终结果：待本次阶段1维护验收。

## B 开发前契约整理记录

日期：2026-09-05

人员：A

角色：项目架构与文档维护

阶段：阶段1（阶段2正式开发前）

任务编号：A1-01

使用工具：Codex

任务目的：阶段2正式开发前，对 B 离线训练、自动实验、模型交付、指标、10轮调参和运行记录契约进行冻结。

Prompt 概括（原始 Prompt 超过 500 字）：阶段2前冻结 B 的数据路径、模型 JSON、实验记录、验收/排序和10轮规则；只改文档、忽略规则和 TODO。禁止训练、数据处理、下载、ROUGE/Benchmark、业务实现及修改架构、接口、Schema、职责或阶段。

涉及文件：README.md、VIBECODING_PROMPT.md、docs/REQUIREMENTS.md、docs/ARCHITECTURE.md、docs/DEVELOPMENT_PLAN.md、docs/AI_PROMPTS.md、.gitignore、model_training/config.yaml、model_training/prepare_cnewsum.py、model_training/train.py、model_training/evaluate.py、model_training/benchmark.py、backend 中仅含失效文档引用的 TODO 注释、runtime/training_runs/.gitkeep。

AI生成内容：B 离线训练数据位置、模型 JSON 交付、实验运行记录、质量/性能验收、候选排序、10轮调参、B/C 依赖与训练依赖边界的文档契约；训练骨架和阶段占位注释仅更新引用/说明。

人工检查：检查冻结架构和公共接口未改变；确认没有读取或处理数据集内容、没有训练、下载、ROUGE、Benchmark 或阶段2实现；检查死链接、Git 忽略、路径和文档字段一致性。

人工修改：待 A 验收补充。

最终结果：完成 B 开发前契约整理，未开始模型训练或阶段2正式实现。

## B 离线训练环境初始化记录

日期：2026-09-05

人员：B

角色：离线训练与模型交付

阶段：阶段2

任务编号：B 阶段2环境初始化

使用工具：Codex

任务目的：为 B 创建独立、可重复的 Windows Python 3.11 离线训练环境初始化脚本。

Prompt 概括（原始 Prompt 超过 500 字）：创建 B 的 requirements 和环境脚本；仅用清华 PyPI 镜像、检测 Python 3.11、复用根目录 .venv 并验证核心包/CUDA。禁止数据处理、下载模型、训练、评价、Benchmark、数据库和公共架构修改。

涉及文件：model_training/requirements.txt、model_training/setup_env.ps1、docs/AI_PROMPTS.md。

AI生成内容：B 独立依赖清单与幂等 PowerShell 初始化脚本；脚本强制当前进程及关键 pip 命令使用清华 PyPI 镜像，并检测 Python、虚拟环境、核心包、PyTorch CUDA 和可选 NVIDIA 信息。

人工检查：连续两次执行脚本。系统未发现 `py -3.11`，`python --version` 为 3.13.2；脚本均在创建 .venv 和安装依赖前以退出码 1 停止。未进行数据处理、模型下载、训练、ROUGE 或 Benchmark。

人工修改：待 B 验收补充。

最终结果：环境初始化脚本已完成；因本机缺少 Python 3.11，尚未创建 .venv 或安装依赖。

## B GPU 环境初始化完善记录

日期：2026-09-05

人员：B

角色：离线训练与模型交付

阶段：阶段2

任务编号：B 阶段2环境初始化完善

使用工具：Codex

任务目的：拆分 PyTorch 安装并完善 NVIDIA/CUDA 检测、官方 wheel 选择与 GPU 验证逻辑。

Prompt 概括（原始 Prompt 超过 500 字）：完善 B 环境脚本：Python 3.11、清华源普通依赖、NVIDIA/驱动/CUDA 检测、官方 PyTorch CUDA wheel 自动选择和实际 Tensor 验证；禁止训练、模型/数据处理及跨模块接口修改。

涉及文件：model_training/requirements.txt、model_training/setup_env.ps1、docs/AI_PROMPTS.md。

AI生成内容：从普通 requirements 移除 torch；脚本为 GPU 选择官方 cu126 wheel，支持 CPU fallback、Torch 幂等检查、完整 import、pip check 与 CUDA Tensor 验证。

人工检查：PowerShell 语法检查通过；真实检测到 NVIDIA GeForce RTX 4080 Laptop GPU、驱动 560.81、驱动 CUDA Runtime 能力 12.6，未检测到 nvcc。实际执行在清华镜像 pip 升级连接被代理重置时停止，未到达 Torch 安装或 GPU Tensor 验证。

人工修改：待 B 验收补充。

最终结果：脚本逻辑已更新；普通依赖镜像连接阻塞，GPU 训练环境尚未完成。

## B PyTorch 下载策略优化记录

日期：2026-09-05

人员：B

角色：离线训练与模型交付

阶段：阶段2

任务编号：B 阶段2环境初始化优化

使用工具：Codex

任务目的：避免重复下载 PyTorch，并按官方稳定 CUDA wheel 矩阵自动选择最高兼容版本。

Prompt 概括（原始 Prompt 超过 500 字）：优化 B 环境脚本：普通包继续清华源；Torch 仅用官方 wheel 源，正确 Torch 完全跳过下载，按已验证官方稳定 CUDA 矩阵选最高兼容 wheel；不训练或修改公共接口。

涉及文件：model_training/setup_env.ps1、docs/AI_PROMPTS.md。

AI生成内容：移除 Torch 强制重装；新增 cu132/cu130/cu126 官方稳定候选矩阵、按 nvidia-smi 驱动能力选择、官方源 Torch 的 `--no-deps` 安装策略。

人工检查：静态检查 PowerShell 语法；未执行 pip 安装或下载。

人工修改：待 B 验收补充。

最终结果：完成下载源与依赖解析策略优化，环境实际安装状态未改变。

## B 实验协议冻结记录

日期：2026-09-05

人员：A

角色：B开发前公共文档维护

阶段：阶段2前

任务编号：B2-01～B2-09 协议冻结

使用工具：Codex

任务目的：冻结 B2-01～B2-09 的数据、评价、资源与实验规则。

Prompt 概括（原始 Prompt 超过 500 字）：冻结 B2-01～B2-09 实验协议：真实 CNewSum split/字段、test isolation、官方 CNewSum ROUGE、最多3候选、10GB、CUDA/OOM、完整留痕；只改文档，不训练或实现。

涉及文件：README.md、VIBECODING_PROMPT.md、docs/REQUIREMENTS.md、docs/ARCHITECTURE.md、docs/DEVELOPMENT_PLAN.md、docs/AI_PROMPTS.md。

AI生成内容：补充数据基线、test 隔离、ROUGE 协议、候选/资源/CUDA/留痕与 B2-01～B2-09 验收规则。

人工检查：仅修改允许文档；未读取或处理数据、下载模型、训练、ROUGE 或 Benchmark。

人工修改：待 A 验收补充。

最终结果：B 开发前实验协议文档冻结。

## AI 审计约束强化记录

日期：2026-09-05

人员：A

角色：项目架构与文档维护

阶段：阶段1/阶段2开发前

任务编号：A1-01

使用工具：Codex

任务目的：强化全员 AI 使用记录与工作区审计。

Prompt 类型：Prompt 概括

完整Prompt：强化全员 AI 使用记录；AI_PROMPTS 为共享审计例外，实际修改必须同步记录，未记录不得完成；新增轻量检查与 /goal 审计规则，不修改业务接口或 Schema。

涉及文件：VIBECODING_PROMPT.md、docs/AI_PROMPTS.md、docs/DEVELOPMENT_PLAN.md、scripts/check_ai_prompt_record.py。

AI 是否实际修改文件：true

AI生成内容：硬性审计规则、共享追加边界和无第三方检查脚本。

人工检查：pending

人工修改：pending

Git commit：pending

最终结果：审计约束与检查脚本已建立。

AI_PROMPTS_PENDING：false

## A 阶段3 业务实现记录

日期：2026-09-05

人员：A

角色：项目架构与文档维护（业务 API 与后端集成）

阶段：阶段3

任务编号：A3-01 / A3-02 / A3-03 / A3-04 / A3-05 / A3-06

使用工具：WorkBuddy（CC 编程助手）

任务目的：实现 A 职责范围内的收藏、反馈、模型指标后端业务：含 Service 静态方法、5 个 API 路由去 NotImplementedError、SQLAlchemy 2.x 双 dialect 让 SQLite 测试与 MySQL 生产共用、conftest 双引擎 fixture、配套 pytest 用例、幂等种子 SQL，以及阶段签字清单更新。

完整Prompt：
```
A（推荐）实现 A3-01~06 + 配套单测
```
后续多轮短指令补完：SQLAlchemy 双 dialect 写法、conftest 双引擎 fixture 设计、test_api/test_database 重写、seed SQL 幂等与字段、API 契约逐字段对齐。

Prompt 类型：Prompt 概括

会话/任务标识：pending

涉及文件：backend/app/services/user_service.py、backend/app/services/model_service.py、backend/app/api/favorites.py、backend/app/api/feedback.py、backend/app/api/model.py、backend/app/models.py、backend/app/dependencies.py、backend/app/exceptions.py、backend/app/schemas.py、backend/tests/conftest.py、backend/tests/test_api.py、backend/tests/test_database.py、sql/seed_test_data.sql、docs/ROLE_A_CHECKLIST.md

AI 是否实际修改文件：true

AI生成内容：UserService 三个静态方法 + upsert_feedback + get_news_user_state；ModelService.get_latest_metrics；5 个 API 路由去掉 NotImplementedError 并按 {code,message,data} 包装；models.py 双 dialect（MYSQL_BIGINT unsigned / SQLITE_INTEGER）；conftest 双引擎 fixture；test_api 15 用例 + test_database 12 用例；seed_test_data.sql 幂等；ROLE_A_CHECKLIST 签字栏。

自动执行范围：仅生成/修改上述 backend/、sql/ 与 docs/ 文件；未改动公共契约路径与字段。

人工检查：cd backend && pytest tests -v 32/32 全绿（SQLite 内存）；逐字段对照 docs/API.md 与 docs/DATABASE.md；公共契约未私自改动。

人工修改：回归实际表名 favorites/feedback（去 AI 幻觉的 user_ 前缀）；rouge DECIMAL 强制转 float；conftest fixture 顺序与事务边界显式 commit+回滚。

人工确认项：A3-07 等 TODO 按角色格式落实；等待真 MySQL 端到端验证。

Git commit：2e1c478（feat(A) 前缀，含阶段3+E2E+GitHub文档，未 push）

最终结果：阶段3 业务实现完整，pytest 32 项 SQLite 全绿。

AI_PROMPTS_PENDING：false

## A E2E 端到端验证记录

日期：2026-09-05

人员：A

角色：项目架构与文档维护（真 MySQL 集成验收）

阶段：阶段3 收尾（衔接阶段5）

任务编号：A3-08（自拟：集成验收）

使用工具：WorkBuddy（CC 编程助手）

任务目的：在本机 MySQL 8.0.45 上跑端到端验证——一条命令覆盖 DB 连接探测、库创建、幂等灌种子、起 uvicorn、9 项 REST 路由契约、pytest 32 项切真 MySQL、收尾 verdict 汇总，期望所有阶段 ALL GREEN。

完整Prompt：
```
真 MySQL 端到端验证
```
后续 7 轮贴 Clipboard_Screenshot.png 逐轮定位 PS 5.1 / pytest / API 契约踩坑。

Prompt 类型：Prompt 概括

会话/任务标识：pending

涉及文件：scripts/run_e2e.ps1（约 502 行）、backend/conftest.py（12 行注释锚点）、sql/seed_test_data.sql（DELETE 顺序倒序）、docs/ROLE_A_CHECKLIST.md

AI 是否实际修改文件：true

AI生成内容：7 阶段 ps1 骨架（conn→create_db→seed→uvicorn→route.contracts→pytest.mysql→summary）；Hit 函数内消化错误返回 hash；Add-Verdict 带诊断上下文；seed 接收 stdout/stderr；pytest 文件重定向 + array splatting。

自动执行范围：ps1 自动跑 mysql/uvicorn/pytest；未改动业务代码与公共契约。

人工检查：本机多轮重跑 run_e2e.ps1，7 轮贴报错截图定位修复，最终 14/14 ALL GREEN；踩坑落 memory/2026-09-05.md 可追溯。

人工修改（7 轮 18 修摘要）：
| # | 踩坑 | 修法 |
|---|---|---|
| 1 | $Host/$Pwd 只读变量同名冲突 | 参数加 P_ 前缀 |
| 2 | 数组字面量 '='+$dbCharset 被拆分 | 先赋 $charsetArg |
| 3 | 表名 AI 幻觉加 user_ 前缀 | 改回 favorites/feedback |
| 4 | ErrorActionPreference=Stop + Hit catch 二次抛错中断 | Hit 内消化 hash |
| 5 | missing_header 期望 422 实际 400 | 期望改 400（pytest 权威） |
| 6 | IWR GetResponseStream 4xx 拿空 | 读 ErrorDetails.Message |
| 7 | here-string 反引号续行 news_id 怪值 | 单变量双引号 here-string |
| 8 | Stop 让 pytest stderr 触发 NativeCommandError | 改 SilentlyContinue |
| 9 | pytest 2>&1 traceback 被吞 | 文件重定向 1> 2> |
| 10 | ModuleNotFoundError app（rootdir 错） | 新建 backend/conftest.py 锚点 + --rootdir |
| 11 | favorite_list 断言 data.items.Count 实际数组 | 改 data.Count |
| 12 | seed 重跑 FK 1451 | 子表先 DELETE |
| 13 | > 重定向 UTF-16 BOM | 顶部三连 encoding utf8 |
| 14 | ps1 与 bash 跑 pytest 结果不同 | dump cmd+DATABASE_URL |
| 15 | Select-Object -Last 1 脆弱 | 正则+3级 fallback |
| 16 | '1>' '2>' 单引号当字符串参数 | 裸 token 1> 2> |
| 17 | runtime/ 缺失 Join-Path 不建 | New-Item -Force |
| 18 | call operator+拼接+Windows 路径 collected 0 | array splatting @pytestArgs |

人工确认项：A3-07/A5/A6 待续；真 MySQL 验证通过但仓库未 push（C 暂未拿到 models.py 双 dialect 修复）。

Git commit：2e1c478（feat(A) 前缀，未 push）

最终结果：run_e2e.ps1 14/14 ALL GREEN，约 502 行，0 解析错；18 条踩坑已落 memory 复用。

AI_PROMPTS_PENDING：false
---

日期：2026-09-05

人员：D

角色：新闻采集/业务/Worker（D-PlutoAkane）

阶段：阶段3

任务编号：D3-11

使用工具：ZCode

任务目的：修复 SummaryService 与 DATABASE.md §8.3 的两处偏差——failed→pending 重试未清 summary_error；complete/fail 未做 CAS 条件更新与失败警告。

Prompt 类型：Prompt 概括

完整Prompt：经逐条审计确认 D3-11 偏差后，用户指示"进行修改"。要求按 DATABASE.md §8.3 实现 CAS 条件更新、CAS 失败记警告不覆盖、重试清空 summary_error，方法签名与对外行为不变。

涉及文件：backend/app/services/summary_service.py、docs/AI_PROMPTS.md。

AI 是否实际修改文件：true

AI生成内容：request_summary/complete/fail 改为 CAS 条件 UPDATE（rowcount=0 记警告不写入）；重试路径清空 summary_error，并发竞争未收敛时抛 409/1003；补 logging 警告与中文 docstring。

人工检查：pending

人工修改：pending

Git commit：pending

最终结果：两处偏差已按冻结契约修复；pytest 31 用例、SQLite CAS 专项冒烟 7/7、真实 MySQL 重试路径冒烟通过，待人工验收与提交。

AI_PROMPTS_PENDING：false

---

日期：2026-09-06

人员：D

角色：新闻采集/业务/Worker（D-PlutoAkane）

阶段：阶段3

任务编号：D3-12

使用工具：ZCode

任务目的：完成骨架中 TODO(D-阶段3) 的 run_worker.ps1 调度入口；移除已完成使命的 verify_d3.py 阶段验收脚本。

Prompt 类型：Prompt 概括

完整Prompt：用户指示"编写这个脚本文件，并删除verify_d3.py脚本文件"。要求按已实现的 python -m app.worker CLI 做参数化透传，显式使用 backend/.venv 解释器，单轮模式配合外部计划任务调度。

涉及文件：scripts/run_worker.ps1、scripts/verify_d3.py（删除）、docs/AI_PROMPTS.md。

AI 是否实际修改文件：true

AI生成内容：run_worker.ps1 参数化实现（venv 解释器校验、UTF-8 控制台、Push-Location、退出码透传、BOM 修复 PowerShell 5.1 中文解析）；真实单轮验证通过（采集+去重+摘要优雅跳过）。

人工检查：pending

人工修改：pending

Git commit：pending

最终结果：调度脚本可交付使用（C2-11 交付后摘要阶段自动生效）；验收脚本按用户指示移除，历史可经 git 追溯。

AI_PROMPTS_PENDING：false

---

日期：2026-09-06

人员：D

角色：新闻采集/业务/Worker（D-PlutoAkane）

阶段：阶段3 维护

任务编号：D3-12（补记）

使用工具：ZCode

任务目的：修复超长文章死循环 bug——C 的 Pipeline 对超 max_input_tokens 文章抛 InputTooLongError，被 Worker 通用 except 标 failed 后经 request_summary 重置回 pending，形成 failed→pending 永久重试循环。

Prompt 类型：Prompt 概括

完整Prompt：用户报告超限文章 failed→pending→failed 死循环，要求把"确定性永久不可处理"与临时失败区分开，最小改动，不破坏 SummaryPipeline.generate() 与状态机公共接口；对超 512 token 文章删除或标记处理，防止进入下一步，按更容易实现的方案执行。

涉及文件：backend/app/exceptions.py、backend/app/ai/pipeline.py、backend/app/services/summary_service.py、backend/app/worker.py、docs/DATABASE.md、backend/tests/test_worker.py、docs/AI_PROMPTS.md。

AI 是否实际修改文件：true

AI生成内容：新增 InputTooLongError 契约异常（exceptions.py 定义、pipeline.py 再导出）；SummaryService.delete_unprocessable 删除外键依赖行与新闻行（CAS 仅 processing）；worker 摘要循环单列 InputTooLongError 分支计入 deleted；DATABASE.md §8.4 补规则；新增 6 项用例。

人工检查：待人工验收；其中 pipeline.py（C 负责文件）与 exceptions.py（公共层文件）为跨角色修改，已在执行后报告，待用户/C 追认异常落点。

人工修改：pending

人工确认项：跨角色修改是否追认。

Git commit：c63cfb4

最终结果：38 项 pytest 全通过；真实库暂无数据变化（流水线未交付，阶段B跳过）；已提示用户 43/72 篇正文超 512 字符，建议与 C 确认 Token Budget 契约。本条为补记，原工作周期遗漏追加。

AI_PROMPTS_PENDING：false

---

日期：2026-09-06

人员：D

角色：新闻采集/业务/Worker（D-PlutoAkane）

阶段：阶段6

任务编号：D6-01、D6-02

使用工具：ZCode

任务目的：补齐阶段6测试缺口——D6-01 Crawler 测试（提取、去噪、映射、去重四维）；D6-02 的 SKIP LOCKED 多 Worker 并发维度（真实 MySQL）。

Prompt 类型：Prompt 概括

完整Prompt：用户引用审计结论（D6-01 未完成、D6-02 并发维度缺失），确认可开始后要求完成这两个测试任务。约束：只新增测试文件与追加本记录，不改既有源码与公共接口。

涉及文件：backend/tests/test_crawlers.py（新增）、backend/tests/test_concurrency_mysql.py（新增）、docs/AI_PROMPTS.md。

AI 是否实际修改文件：true

AI生成内容：20 项 crawler 用例（内嵌 HTML 夹具 + monkeypatch 隔离网络，覆盖提取/去噪/图注剔除/标题链/六类映射/结构一致/SHA-256 去重与校验拒绝）；5 项并发用例（FOR UPDATE SKIP LOCKED 跳过被锁行确定性验证、4 线程×24 条恰一次领取、仅领 pending、CAS 重置单胜者与幂等、processing 不被重置），连真实 MySQL 但建独立 {db_name}_e2e 库（应用用户建库失败时按本机免密 root 约定引导，TEST_MYSQL_ROOT_PASSWORD 可覆盖，用例始终以 news_app 身份运行），结束后删库，真实业务库只读不碰。

自动执行范围：本地 pytest 运行、e2e 库建删；未 push。

人工检查：pending

人工修改：pending

人工确认项：无。

Git commit：pending

最终结果：全套 pytest 63/63 通过（58 SQLite + 5 MySQL 并发）；真实库 news_summary 数据原样（72 篇），e2e 库已自动删除。遗留：§9 要求的 scripts/check_ai_prompt_record.py 在仓库中不存在，无法执行该检查，已报告待 A 补齐。

AI_PROMPTS_PENDING：false

## B CNewSum test 短文本子集诊断记录

日期：2026-09-06

人员：B

角色：离线训练与模型诊断

阶段：阶段2诊断

任务编号：B2-DIAG-TEST-LT512

使用工具：Codex

任务目的：以已导出的正式 Seq2Seq 模型诊断 CNewSum 正式 test 中不发生 512-token 输入截断样本的质量。

Prompt 类型：Prompt 概括

完整Prompt：快照并保护正式 test，以正式模型 tokenizer 严格筛选 token_count<512 的原序子集，复用固定生成与 ROUGE 评价，保存逐样本预测/指标；不得训练、改权重、跑全量 test、调参、改业务或宣称正式验收通过。

涉及文件：model_training/b2_diag_test_lt512.py、runtime/datasets/derived/cnewsum_test_lt512/、runtime/training_runs/b2-diag-test-lt512-20260905T154936Z/、docs/AI_PROMPTS.md。

AI 是否实际修改文件：true

AI生成内容：可复现的原始 test 快照、严格短文本派生集、CUDA 诊断评价、5,439 条真实预测与 ROUGE 记录；原 test 与正式模型文件指纹保持不变。

自动执行范围：仅 B 的 model_training/、runtime/ 与本审计追加例外；未修改模型权重、公共接口、业务代码或其他说明文档。

人工检查：pending

人工修改：pending

人工确认项：该结果是 test_lt512 诊断结果，不能作为完整 test/Pipeline 验收结论。

Git commit：pending

最终结果：完成。ROUGE-L=0.46397070848972705，quality_pass_rate=0.5984555984555985，正式全量 test 未运行。

AI_PROMPTS_PENDING：false

## B 阶段2 B2-01～B2-09 执行记录

日期：2026-09-05

人员：B

角色：离线训练与模型交付

阶段：阶段2

任务编号：B2-01～B2-09

使用工具：Codex

Prompt 概括：完成 B2-01～B2-09：审计和标准化 CNewSum，严格隔离 test，按官方兼容 ROUGE 调查至多三名候选、CUDA 训练与最多十轮调优，完整记录实验并导出模型；预算 10GB，不执行 B2-10 以后任务。

涉及文件：model_training/、runtime/datasets/、runtime/training_runs/、runtime/models/、docs/AI_PROMPTS.md。

AI生成内容：完成可复现数据审计、标准化、统计、官方兼容 ROUGE、候选验证、CUDA 训练、完整 dev 评价和本地模型导出；B2-07 完整 train 微调耗时 18,351.819499 秒、峰值显存 6,455,761,920 字节，B2-08 覆盖 14,356 条 dev，B2-09 local_files_only 重载及 dev 冒烟通过。

人工检查：pending（未伪造人工检查或提交）。

人工修改：待补充。

最终结果：B2-01～B2-09 完成；test 保持 held-out，未运行 test 模型评价；未执行 B2-10 以后任务。

## B 分支提交整理记录

日期：2026-09-06

人员：B

角色：离线训练与模型交付

任务编号：B-GIT-ORGANIZATION

使用工具：Codex

Prompt 概括：将 B 开发整理至独立 B 分支，只提交可复现训练、评价源码、配置和测试；排除数据、模型、checkpoint、cache、运行产物与虚拟环境，不覆盖 main、C 或其他角色分支，不强推。

涉及文件：model_training/、docs/AI_PROMPTS.md。

AI 是否实际修改文件：true

人工检查：pending

人工修改：pending

Git commit：pending

最终结果：待完成提交与远程推送验证。

AI_PROMPTS_PENDING：false

## 新闻 token 长度范围文档冻结

日期：2026-09-06

人员：A

角色：项目文档维护

任务编号：文档范围冻结（未变更任务编号或任务表）

使用工具：Codex

Prompt 类型：Prompt 概括

完整Prompt：仅更新新闻正文 token 长度限制相关文档：使用正式 Seq2Seq/T5 tokenizer 未截断计数不超过 512 tokens；超长由 Pipeline 抛 InputTooLongError，Worker 事务删除。不得修改实现、训练、数据库结构、任务表或其他角色需求。

涉及文件：README.md、VIBECODING_PROMPT.md、docs/REQUIREMENTS.md、docs/ARCHITECTURE.md、docs/API.md、docs/DATABASE.md、docs/AI_PROMPTS.md。

AI 是否实际修改文件：true

AI生成内容：统一长度判定、禁止 silent truncation、超长内部删除事务、既有 404 语义，以及 eligible test subset 的统计口径；未调整角色任务、阶段依赖、验收门槛或性能指标。

自动执行范围：仅上述 Markdown 文档；未修改 Python、PowerShell、SQL、数据库、模型或训练产物。

人工检查：pending。

人工修改：pending。

Git commit：本次提交（仅新闻 token 长度范围相关文档）。

最终结果：已完成文档一致性检查，等待人工审查。

AI_PROMPTS_PENDING：false

---

日期：2026-09-06

人员：D

角色：新闻采集/业务/Worker（D-PlutoAkane）

阶段：阶段3 维护（merge readiness）

任务编号：D3-11/D3-12/D3-13 维护 + D6-02 补强

使用工具：ZCode

任务目的：按外部审查核实并修复 merge blocker——同步最新 main；delete_unprocessable 原子事务；run_worker.ps1 与根 .venv 统一；news_id Path(gt=0) 422 契约；恢复 AI_PROMPTS_我的.md。

Prompt 类型：Prompt 概括

完整Prompt：用户提供外部审查报告（指出落后 main 需同步、delete_unprocessable 在父记录 CAS 失败时仍 commit 导致"子表已删新闻仍在"、run_worker.ps1 找 backend/.venv 与新 setup_runtime_env.ps1 的根 .venv 冲突、news_id 缺 Path(gt=0) 422、AI_PROMPTS_我的.md 被误删），要求仔细检查是否有严重 bug 并修复。

涉及文件：backend/app/services/summary_service.py、backend/app/worker.py、backend/app/api/news.py、backend/tests/test_worker.py、backend/tests/test_api.py、scripts/run_worker.ps1、docs/DATABASE.md（合并）、docs/AI_PROMPTS.md、docs/AI_PROMPTS_我的.md（恢复）。

AI 是否实际修改文件：true

AI生成内容：逐项核实后合并 origin/main（e86cdd0，无冲突）；delete_unprocessable 改为单事务三步 DELETE、CAS 失败或异常整事务 rollback 并返回 -1，worker 据实打印且不计 deleted 统计；新增"CAS 失败依赖行原样保留"回归测试（旧实现下必失败）；news.py 两路由加 Annotated[int, Path(gt=0)] 并补 4 项 API 契约测试（详情字段/404/422×4/202）；run_worker.ps1 根 .venv 优先、backend\.venv 过渡回退，真实冒烟通过。

自动执行范围：本地 pytest、run_worker.ps1 冒烟；未 push。

人工检查：pending

人工修改：pending

人工确认项：stale processing 自动恢复与 main DATABASE.md §8.4"不强制超时重置"的表述差异，建议 A 修订文档保留代码；A 的 favorites/feedback 三路由同样缺 Path(gt=0)，属 A 文件待 A 处理。

Git commit：pending

最终结果：全套 pytest 68/68 通过（63 SQLite 侧 + 5 MySQL 并发）；main 7ea7d0c 已将 InputTooLongError 契约与 delete_unprocessable 事务要求冻结进文档，此前跨角色待追认项闭环。AI_PROMPTS_PENDING：false

## A 阶段3集成：合并main（B训练代码+D新闻业务）记录

日期：2026-09-06

人员：A

角色：项目集成与文档（阶段3收尾同步）

任务目的：将远端 main 合入 A 分支，使本地同时具备 A 业务 API、B 训练代码（b2_* 全套）、D 爬虫/新闻业务/Worker 及其 merge readiness 修复包；修复工作区索引污染（output/ 产物与嵌套目录被误 stage、download_mysql.ps1 与 AI_PROMPTS_我的.md 被删），恢复文件并提交阶段3 AI 记录；union 解决 AI_PROMPTS.md 双侧追加冲突；安装 beautifulsoup4/lxml 新依赖；合并后 pytest 63 passed / 5 skipped（MySQL 并发用例跳过）。

完整Prompt：
```
查看现在的文件，看看之前三阶段的能不能做了
好的
```

修改文件：backend/*（合并）、model_training/*（合并）、scripts/*（合并+恢复）、docs/AI_PROMPTS.md（记录追加+冲突合并）、docs/AI_PROMPTS_我的.md（恢复）。

使用公共接口：无新增；未改动任何冻结契约。

结果：合并提交 4b5122f 推送至 origin/A；pytest 63 passed, 5 skipped。

AI_PROMPTS_PENDING：false
