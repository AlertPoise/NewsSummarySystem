# HarmonyOS 客户端实施说明

E 在阶段 4 创建正式 DevEco Studio 工程，工程根目录为 `frontend_harmony/`。不得伪造本次完整工程，也不得让客户端直连 MySQL 或 Python AI。

推荐正式目录：

```text
entry/src/main/ets/
├── pages/Index.ets、MainPage.ets、NewsDetailPage.ets
├── view/HomeView.ets、FavoriteView.ets、AboutView.ets、NewsCard.ets、SummaryCard.ets
├── viewmodel/NewsViewModel.ets、FavoriteViewModel.ets
├── model/News.ets
└── common/ApiConfig.ets、HttpClient.ets、ClientIdManager.ets
```

调用层级固定为 `Page/View → ViewModel → HttpClient → FastAPI`。`ClientIdManager` 生成 UUID 并存入 Preferences；所有收藏和反馈请求使用 `X-Client-ID`。首页按六类分类展示新闻，支持刷新和分页；详情展示标题、来源、发布时间、AI 摘要、正文、收藏和反馈；关于页从 `GET /api/model/metrics` 获取真实指标。

TODO(E-阶段4)：创建以上正式 ArkTS/ArkUI 工程并完成所有页面、状态和网络调用；输入为 docs/API.md 的冻结 API 与 schemas.py 字段，输出为可在 HarmonyOS 设备或模拟器运行的客户端，必须遵守 docs/ARCHITECTURE.md。
