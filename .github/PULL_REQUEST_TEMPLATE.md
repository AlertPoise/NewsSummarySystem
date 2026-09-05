## 概述

清晰简洁地说明本 PR 做了什么、为什么。

## 关联

- 任务编号：`A3-xx` / `B2-xx` / `C2-xx` / `D3-xx` / `E4-xx` ...
- 关联 Issue：`#123`
- 关联讨论：链接或描述

## 涉及角色与文件

按 [`README.md`](../../README.md) 表格填：

- 角色：
- 主要改动文件：
- 顺带改动文件：
- 是否改动其他角色主要负责文件：是 / 否（如是，已取得用户授权：是 / 否）

## 公共契约影响

按 [`CONTRIBUTING.md` §4.4](../../CONTRIBUTING.md#44-重大变更门槛) 勾选：

- [ ] REST 路径或公共字段变化
- [ ] 数据库 Schema 变化
- [ ] `RawArticle` / `SummaryPipeline` / `SummaryResult` / 模型交付字段变化
- [ ] 用户状态内部接口 / 摘要状态机变化
- [ ] 新增 / 替换冻结技术栈组件
- [ ] 无上述影响

如勾选任一项，请贴出 `DEVELOPMENT_PLAN.md` 中对应更新章节的链接。

## 改动类型

- [ ] 新功能
- [ ] 缺陷修复
- [ ] 文档
- [ ] 重构（不影响公共契约）
- [ ] 测试用例
- [ ] 工程改进（CI / 依赖 / 工具）
- [ ] 数据集 / 模型交付（仅 B 角色）

## 测试与验证

- [ ] pytest 本地全过（SQLite）：`cd backend && .venv/Scripts/python -m pytest tests -v`
- [ ] pytest MySQL 模式全过：环境变量 `TEST_MYSQL_URL` 切换后 32 项全绿
- [ ] `scripts/run_e2e.ps1` 端到端 14/14 ALL GREEN
- [ ] 已人工核对受影响文件无伪造结果、无残留 `.env` / 临时文件
- [ ] 已运行 `git status` 确认无意外改动

实际跑过的命令与输出（截选关键几行即可）：

```text
（粘贴此处）
```

## AI 使用记录

是否调用 AI 协助本次 PR：

- [ ] 否（人工提交）
- [ ] 是（已在 `docs/AI_PROMPTS.md` 当个工作周期内追加记录，任务编号：________）

## 公开 TODO

提交后留下哪些 TODO，按 VIBECODING 模板：

- `TODO(角色)：任务描述 / 输入 / 输出 / 依赖接口`

## Checklist

- [ ] 阅读并遵守了 `VIBECODING_PROMPT.md`
- [ ] 阅读并遵守了 `CONTRIBUTING.md`
- [ ] `CHANGELOG.md` 已同步更新对应阶段条目
- [ ] 角色对应清单（如 `ROLE_A_CHECKLIST.md`）已签字
- [ ] 没有伪造任何新闻、摘要、ROUGE 或性能数据
- [ ] 没有引入未冻结技术
- [ ] 没硬编码密码、个人 IP、个人绝对路径
- [ ] 注释 / docstring / TODO 全部中文
