# REST API 冻结

所有地址前缀为 `/api`。成功响应固定为 `{"code":0,"message":"ok","data":...}`；错误响应为 `{"code":非0整数,"message":"错误信息","data":null}`，并使用正确 HTTP 状态码。除健康检查外，以下业务端点由阶段 3 实现。

| 接口 | 请求与负责人 | 成功 data | 错误与状态码 |
|---|---|---|---|
| `GET /health` | 无参数；A，阶段1 | `{"status":"healthy"}` | 500：服务内部错误 |
| `GET /categories` | 无参数；D，阶段3 | `string[]`，仅实际存在的系统分类 | 500：查询失败 |
| `GET /news` | Query：`page` 默认1且≥1，`page_size` 默认20且最大50，`category` 可选；D，阶段3 | `{"items":[{"id","title","summary","category","source","publish_time","summary_status"}],"page","page_size","total"}`，按 publish_time DESC，绝不含 content | 422：参数非法；500：查询失败 |
| `GET /news/{news_id}` | Path：news_id；Header：可选 `X-Client-ID`；D，阶段3 | `{"id","title","content","summary","category","source","source_url","publish_time","summary_status","summary_time_ms","is_favorite","feedback"}`；无 header 时 false/null | 404：新闻不存在；500：查询失败 |
| `POST /news/{news_id}/summary` | Path：news_id；D，阶段3 | `{"news_id","summary_status","summary","generation_time_ms"}`；completed 返回已有摘要，processing 返回状态，pending 允许生成，failed 允许重试 | 404：不存在；409：并发状态冲突；503：AI 不可用；500：生成失败 |
| `GET /favorites` | 必填 Header：`X-Client-ID`；A，阶段3 | `NewsListItem[]` | 400：缺少或非法 client id；500：查询失败 |
| `POST /favorites/{news_id}` | 必填 Header：`X-Client-ID`，Path：news_id；A，阶段3 | 收藏后的新闻标识或状态；重复收藏仍成功且幂等 | 400：client id 无效；404：新闻不存在；500：保存失败 |
| `DELETE /favorites/{news_id}` | 必填 Header：`X-Client-ID`，Path：news_id；A，阶段3 | 取消结果 | 400：client id 无效；404：新闻或收藏不存在；500：删除失败 |
| `POST /news/{news_id}/feedback` | 必填 Header：`X-Client-ID`；Body：`{"helpful":true}`；A，阶段3 | 当前评价结果；同一 client/news 不存在则 INSERT，存在则 UPDATE | 400：header/body 无效；404：新闻不存在；500：保存失败 |
| `GET /model/metrics` | 无参数；A，阶段3 | `{"model_name","model_version","dataset","dataset_split","sample_count","rouge1","rouge2","rougeL","avg_generation_time_ms","p95_generation_time_ms"}`，最新正式 CNewSum 结果 | 404：无正式评价；500：查询失败 |

Pydantic 字段以 `backend/app/schemas.py` 为唯一代码定义。路由只能调用 Service，Service 才能调用 SQLAlchemy；摘要路由只能经 `SummaryService` 调用 `SummaryPipeline.generate(article)`。
