---
name: 缺陷报告
about: 提交后端 / 数据 / 客户端缺陷，请按模板填写
title: "[Bug] <一句话描述>"
labels: bug
assignees: ''
---

## 现象描述

清晰简洁地描述发生了什么。

## 复现步骤

1. ...
2. ...
3. ...

## 期望行为

清晰简洁地描述你期望发生什么。

## 实际行为

发生了什么，错误码、堆栈、截图等。

## 环境信息

- OS / 版本：[e.g. Windows 11 23H2]
- Python：[e.g. 3.11.9]
- MySQL：[e.g. 8.0.45]
- 后端 commit / 分支：[e.g. main @ abc1234]
- 客户端：[e.g. DevEco Studio 5.0.3]
- 其他：浏览器 / HarmonyOS 模拟器版本

## 涉及模块

按 [`README.md`](../../README.md) 角色勾选：

- [ ] A：架构 / 数据库 Schema / FastAPI 公共规范 / 收藏 / 反馈 / 模型指标
- [ ] B：CNewSum / 训练 / 模型 / ROUGE
- [ ] C：文本预处理 / BERT / TextRank / Token Budget / 在线摘要
- [ ] D：新闻源 / 爬虫 / Worker / 新闻 API
- [ ] E：HarmonyOS 客户端
- [ ] 不确定 / 跨模块

## 可能根因（可选）

猜一下，方便 reviewer 快速定位。

## 复现命令 / 截图 / 日志

如有可一键复现的命令（`pytest tests/test_X.py::test_y`、`scripts/run_e2e.ps1`）或日志片段，请直接贴。

```text
（粘贴此处）
```

## 严重程度 / 优先级

- [ ] Blocker（主线阻塞）
- [ ] Major（影响核心交付）
- [ ] Minor（边缘场景）
- [ ] Cosmetic（文档 / 排版）
