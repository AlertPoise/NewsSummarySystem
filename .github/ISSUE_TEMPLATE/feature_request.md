---
name: 功能请求
about: 提交新功能或显著改进建议
title: "[Feature] <一句话描述>"
labels: enhancement
assignees: ''
---

## 提议功能

清晰简洁地描述你想加什么。

## 动机 / 价值

为什么需要它，解决了什么问题；最好附真实场景。

## 拟改动范围

按 [`README.md`](../../README.md) 角色勾选将涉及的模块：

- [ ] A：架构 / 数据库 Schema / FastAPI 公共规范 / 收藏 / 反馈 / 模型指标
- [ ] B：CNewSum / 训练 / 模型 / ROUGE
- [ ] C：文本预处理 / BERT / TextRank / Token Budget / 在线摘要
- [ ] D：新闻源 / 爬虫 / Worker / 新闻 API
- [ ] E：HarmonyOS 客户端
- [ ] 跨多角色
- [ ] 不确定

## 对公共契约的可能影响

- [ ] 改动 REST 路径 / 字段
- [ ] 改动数据库 Schema
- [ ] 改动 `RawArticle` / `SummaryPipeline` / `SummaryResult` / 模型交付字段
- [ ] 改动用户状态内部接口 / 摘要状态机
- [ ] 引入未冻结技术（Redis / Kafka / Celery / Docker / K8s / JWT 等）
- [ ] 无影响

## 备选方案（可选）

考虑过的其他实现路径与权衡。

## 验收 / 测试想法

如何确认这个功能按预期工作：

- 单元测试
- pytest 集成用例
- 端到端脚本 `scripts/run_e2e.ps1`
- HarmonyOS 端可见效果
- ROUGE / 性能指标

## 优先级 / 时间窗

- [ ] 阶段 4 内必须
- [ ] 阶段 5 内应当
- [ ] 阶段 6 之前可以
- [ ] Nice to have
