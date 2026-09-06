# REST API 契约冻结

## 1. 统一规则

前缀固定为 `/api`。所有成功响应为 `{"code":0,"message":"ok","data":...}`，错误响应为 `{"code":非0整数,"message":"错误描述","data":null}`。时间字段均为 ISO 8601 字符串；数据库内部保存 DATETIME。业务错误码固定：1001 输入/请求头非法，1002 资源不存在，1003 状态冲突，1004 AI 不可用，1005 内部业务失败。HTTP 400 用于 Header 或业务输入非法，404 为资源不存在，409 为状态冲突，422 为 FastAPI 参数校验失败，500 为内部错误，503 为正式 AI 不可用。

`X-Client-ID` 必须为 UUID v4 标准字符串，例如 `550e8400-e29b-41d4-a716-446655440000`。必填端点缺失或格式错误时返回 400/1001；新闻详情可省略，省略时 `is_favorite=false`、`feedback=null`。

## 2. 接口清单

| 接口 | 负责人 | 调用者 | 幂等性/并发语义 |
|---|---|---|---|
| GET /health | A | 运维、客户端调试 | 只读 |
| GET /categories | D | E | 只读，固定六类 |
| GET /news | D | E | 只读，稳定排序 |
| GET /news/{news_id} | D/A | E | 只读，复用用户状态服务 |
| POST /news/{news_id}/summary | D | E | 不执行推理；仅状态触发/重试 |
| GET /favorites | A | E | 只读，client 隔离 |
| POST /favorites/{news_id} | A | E | 幂等：重复收藏成功 |
| DELETE /favorites/{news_id} | A | E | 幂等：重复取消成功 |
| POST /news/{news_id}/feedback | A | E | 同一 client/news 更新当前评价 |
| GET /model/metrics | A | E | 只读，返回最新正式结果 |

## 3. 健康检查：GET /api/health

负责人 A；调用者为运维或客户端调试。无 Header、Path、Query、Body。成功 HTTP 200：

```json
{"code":0,"message":"ok","data":{"status":"healthy"}}
```

服务异常返回 HTTP 500/1005。只读幂等。

## 4. 分类：GET /api/categories

负责人 D；调用者 E。无 Header、Path、Query、Body。成功 HTTP 200，`data` 为 `string[]`，且始终按以下稳定顺序返回：

```json
{"code":0,"message":"ok","data":["科技","财经","社会","体育","国内","国际"]}
```

查询失败为 HTTP 500/1005。只读幂等；不得改为“数据库当前存在的分类”。

## 5. 新闻列表：GET /api/news

负责人 D；调用者 E。无 Header、Path、Body。Query：`page:int`，可选、默认 1、最小 1；`page_size:int`，可选、默认 20、范围 1~50；`category:string|null`，可选，若提供必须为六个系统分类之一。排序固定为 `publish_time DESC`；publish_time 为 null 的记录排在非空记录之后，null 内按 `id DESC`，非空同时间按 `id DESC`，确保稳定分页。

成功 HTTP 200：

```json
{"code":0,"message":"ok","data":{"items":[{"id":123,"title":"标题","summary":null,"category":"科技","source":"来源","publish_time":"2026-09-04T10:00:00","summary_status":"pending"}],"page":1,"page_size":20,"total":1}}
```

`id:int`、`title:string`、`category:string`、`source:string`、`summary_status:string` 非空；`summary:string|null`、`publish_time:string|null` 可空。禁止返回 `content`。参数类型或范围错误为 HTTP 422；非法 category 为 HTTP 400/1001；查询失败为 HTTP 500/1005。只读幂等。

## 6. 新闻详情：GET /api/news/{news_id}

负责人 D（新闻）和 A（用户状态）；调用者 E。Path `news_id:int` 必填且大于 0；Header `X-Client-ID:UUID v4` 可选；无 Query、Body。成功 HTTP 200：

```json
{"code":0,"message":"ok","data":{"id":123,"title":"标题","content":"新闻正文","summary":"最终摘要","category":"科技","source":"来源","source_url":"https://example.invalid/news/123","publish_time":"2026-09-04T10:00:00","summary_status":"completed","summary_time_ms":860,"is_favorite":true,"feedback":true}}
```

`id/title/content/category/source/source_url/summary_status/is_favorite` 非空；`summary`、`publish_time`、`summary_time_ms`、`feedback` 可空。无 X-Client-ID 时固定 `is_favorite=false`、`feedback=null`。news_id 不存在为 HTTP 404/1002；这同样适用于被 Worker 因 InputTooLongError 删除的范围外新闻，不新增公开错误码或暴露内部异常。header 格式错误为 HTTP 400/1001；Path 校验错误为 422；查询失败为 500/1005。只读幂等，D 必须通过 `UserService.get_news_user_state` 获取用户状态。

## 7. 摘要任务：POST /api/news/{news_id}/summary

负责人 D；调用者 E。Path `news_id:int` 必填且大于 0；无 Header、Query、Body。响应 data 固定为 `news_id:int`、`summary_status:string`、`summary:string|null`、`generation_time_ms:int|null`。

completed 时 HTTP 200，返回已有摘要：

```json
{"code":0,"message":"ok","data":{"news_id":123,"summary_status":"completed","summary":"最终摘要","generation_time_ms":860}}
```

processing、pending 及 failed 重置为 pending 时均返回 HTTP 202：

```json
{"code":0,"message":"ok","data":{"news_id":123,"summary_status":"pending","summary":null,"generation_time_ms":null}}
```

该接口不在 HTTP 线程调用 Transformer；Worker 是唯一正式 AI 调用者。对同一新闻并发请求不得重复创建摘要工作：已 processing 返回 processing；pending 只确认 pending；failed 原子重置 pending。news_id 不存在为 404/1002；这同样适用于已因 InputTooLongError 被 Worker 删除的范围外新闻。InputTooLongError 是 Worker 内部范围处理结果，不作为新的 HTTP 类型暴露。无法原子变更状态为 409/1003；正式 AI 系统不可用为 503/1004；内部失败为 500/1005。

## 8. 收藏列表：GET /api/favorites

负责人 A；调用者 E。Header `X-Client-ID:UUID v4` 必填；无 Path、Query、Body。成功 HTTP 200：

```json
{"code":0,"message":"ok","data":[{"id":123,"title":"标题","summary":"摘要","category":"科技","source":"来源","publish_time":"2026-09-04T10:00:00","summary_status":"completed"}]}
```

项目字段与新闻列表项相同，`summary`、`publish_time` 可空，绝不返回 content。缺失/错误 header 为 400/1001；查询失败为 500/1005。只读幂等，仅返回该 client_id 的收藏。

## 9. 收藏：POST /api/favorites/{news_id}

负责人 A；调用者 E。Header `X-Client-ID:UUID v4` 必填；Path `news_id:int` 必填且大于 0；无 Query、Body。成功 HTTP 200：

```json
{"code":0,"message":"ok","data":{"news_id":123,"is_favorite":true}}
```

`news_id:int`、`is_favorite:bool` 均非空。首次调用 INSERT；同一 client_id/news_id 重复调用不新增记录且仍返回同一成功响应。header 错误为 400/1001，新闻不存在为 404/1002，Path 校验为 422，保存失败为 500/1005。

## 10. 取消收藏：DELETE /api/favorites/{news_id}

负责人 A；调用者 E。Header 和 Path 与收藏一致，无 Query、Body。成功 HTTP 200：

```json
{"code":0,"message":"ok","data":{"news_id":123,"is_favorite":false}}
```

重复取消也幂等成功，即没有收藏记录时仍返回 `is_favorite=false`。header 错误为 400/1001，新闻不存在为 404/1002，Path 校验为 422，删除失败为 500/1005。

## 11. 摘要反馈：POST /api/news/{news_id}/feedback

负责人 A；调用者 E。Header `X-Client-ID:UUID v4` 必填；Path `news_id:int` 必填且大于 0；无 Query。Body 必填：

```json
{"helpful":true}
```

`helpful:bool` 不可空。成功 HTTP 200：

```json
{"code":0,"message":"ok","data":{"news_id":123,"helpful":true}}
```

首次为 INSERT，后续同一 client_id/news_id 为 UPDATE，只保留一个当前评价。header 或业务输入错误为 400/1001，Body/Path 结构校验为 422，新闻不存在为 404/1002，保存失败为 500/1005。请求可重复，最终状态以最后一次 successful request 为准。

## 12. 模型指标：GET /api/model/metrics

负责人 A；调用者 E。无 Header、Path、Query、Body。成功 HTTP 200：

```json
{"code":0,"message":"ok","data":{"model_name":"正式模型名称","model_version":"正式版本","dataset":"CNewSum","dataset_split":"test","sample_count":1000,"rouge1":0.0,"rouge2":0.0,"rougeL":0.0,"avg_generation_time_ms":0,"p95_generation_time_ms":0}}
```

示例数值仅表示字段类型，不能作为模型实测结果。`model_name/model_version/dataset/dataset_split:string`、`sample_count/avg_generation_time_ms/p95_generation_time_ms:int`、`rouge1/rouge2/rougeL:number` 全部非空；dataset 固定 CNewSum、dataset_split 固定 test。无正式评价记录为 404/1002，查询失败为 500/1005。只读幂等。
