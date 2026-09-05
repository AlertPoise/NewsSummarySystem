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
