# 测试计划与验收

| 类别 | 覆盖内容 | 负责人 | 阶段 |
|---|---|---|---|
| AI 单元测试 | 清洗、分句、BERT 批处理、TextRank、Token Budget、异常和 Pipeline 契约 | C | 2、6 |
| 数据库测试 | 字段、外键、状态约束、收藏/反馈唯一约束 | A | 3、6 |
| API 测试 | 状态码、统一 JSON、分页、header、幂等、错误路径 | A/D | 3、6 |
| Crawler 测试 | 两来源字段提取、噪声清理、分类映射、哈希去重 | D | 3、6 |
| Worker 测试 | pending/processing/completed/failed、并发互斥、结果持久化 | D/C | 3、6 |
| HarmonyOS 测试 | UUID、刷新、分页、详情、收藏、反馈、网络/加载/空状态 | E | 4、6 |
| 系统集成测试 | 真实网站到客户端全链路和所有用户功能 | 全员，A主导 | 5、6 |
| ROUGE 最终验收 | CNewSum test 的 ROUGE-1/2/L，ROUGE-L ≥ 0.40，写库 | B | 2、6 |
| 性能最终验收 | 预热、batch size=1，从 generate 到字符串结束；记录平均/P95，单篇<1.5秒 | B/C | 2、6 |

测试数据、命令、环境、预期和实测结果在阶段 6 写入实践文档。不得以 Mock 结果替代阶段 5 的真实端到端验证。
