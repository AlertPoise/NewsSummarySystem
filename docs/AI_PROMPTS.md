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
