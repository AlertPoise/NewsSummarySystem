# HarmonyOS 客户端实施说明（E 角色）

E 在阶段 4 交付正式 DevEco Studio 工程，工程根目录为 `frontend_harmony/`。客户端不直连 MySQL、不调用 Python AI；所有数据经 `docs/API.md` 冻结 REST 契约获取。

## 1. 当前状态（阶段 4 完成，E4-01~E4-19）

- E4-01 正式工程：DevEco Studio 5.0.0 工程（HarmonyOS 5 / API 12，Stage 模型），可导入 DevEco 后直接构建签名运行。
- E4-02 HttpClient：统一请求层，仅按 `docs/API.md` 实现，含统一包装解析、业务码（1001~1005）与 HTTP 状态映射、超时控制。
- E4-03 Client ID：`ClientIdManager` 生成 UUID v4 并持久化到 Preferences；收藏/反馈/详情用户状态请求自动附加 `X-Client-ID`。
- E4-04 数据 Model：`model/News.ets` 字段名与 API JSON 完全一致。
- E4-05 MainPage 框架：底部 Tab——首页 / 收藏 / 关于。
- E4-06 分类：首页分类来自 `GET /api/categories`（六类稳定顺序），不做额外硬编码分类（“全部”仅为客户端本地筛选）。
- E4-07 新闻列表：`GET /api/news` 卡片列表（不含 content）。
- E4-08 分页：触底加载，page_size=20（遵守 1~50）。
- E4-09 刷新：下拉刷新 + 顶部“刷新”，复位第一页与状态。
- E4-10 新闻详情：`GET /api/news/{news_id}`，可选 X-Client-ID 正确处理（无 ID 时服务端返回 is_favorite=false/feedback=null）。
- E4-11 AI 摘要：按 summary_status 状态机展示 pending/processing/completed/failed；仅 POST `/api/news/{id}/summary` 触发任务；任务接受后有限轮询详情接口等待最终结果，不伪造处理结果。
- E4-12 全文：详情页展示 content。
- E4-13 收藏操作：收藏/取消收藏遵循幂等语义，界面状态以服务端响应为准。
- E4-14 收藏列表：`GET /api/favorites`（仅当前 client），详情页收藏变化后自动刷新。
- E4-15 摘要反馈：有帮助/没帮助可重复更新（同 client/news 覆盖）。
- E4-16 模型指标：关于页 `GET /api/model/metrics` 真实数据展示，无评价记录时按空态处理，不硬编码指标。
- E4-17~19 Loading/Empty/Error：首页、收藏、详情、指标均有独立加载/空/错误态，错误显示可理解文案并可重试。

## 2. 调用层级

固定为 `Page/View → ViewModel → HttpClient → FastAPI`，目录结构见 README 仓库约定的推荐布局：

```text
entry/src/main/ets/
├── pages/            Index.ets、MainPage.ets、NewsDetailPage.ets
├── view/             HomeView/FavoriteView/AboutView/NewsCard/SummaryCard/Loading/Empty/Error
├── viewmodel/        NewsViewModel/NewsDetailViewModel/FavoriteViewModel/MetricsViewModel
├── model/            News.ets（契约字段模型与解析）
├── common/           ApiConfig/HttpClient/ClientIdManager/JsonUtil/Formatters
└── entryability/     EntryAbility.ets
```

## 3. 运行步骤（模拟器）

1. 用 DevEco Studio 5.0.x 打开本目录，等待 Sync 完成（首次需配置 HarmonyOS SDK；签署请使用 DevEco 自动签名）。
2. 后端以 `python -m uvicorn app.main:app --host 0.0.0.0 --port 8000` 启动（见根目录 `docs/WINDOWS_SETUP.md`）。
3. 默认 `ApiConfig.baseUrl = http://10.0.2.2:8000`（模拟器访问宿主机）；真机请改 `entry/src/main/ets/common/ApiConfig.ets` 为后端局域网地址并在防火墙放行 8000 端口。
4. 运行 entry 到模拟器/真机：首页分类 → 列表 → 详情 → 摘要/收藏/反馈 → 收藏页 → 关于页指标。

## 4. 阶段 4 验收对照

阶段 4 验收（docs/DEVELOPMENT_PLAN.md）：完整客户端支持分类、列表、分页、刷新、详情、摘要、全文、收藏、反馈、指标及 Loading/Empty/Error 状态，所有数据经 API —— 本工程已按契约实现。

说明：摘要 processing 的“处理中”与最终摘要均来自服务端状态机；若后端 Worker 未运行，摘要状态会停留在 pending/processing，属后端侧预期行为而非客户端伪造。

## 5. 后续阶段（E6，待阶段 5 联调后进行）

- E6-01：在模拟器/真机配合后端完成全功能与异常状态测试并记录；
- E6-02：真实页面截图与演示流程（本目录 docs/ 下归档）；
- E6-03：端到端演示视频。

## 6. 历史

- TODO(E-阶段4)（原始占位）已由 E4-01~E4-19 完成并替换为本说明。
