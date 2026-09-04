$BackendDirectory = Join-Path $PSScriptRoot "..\backend"

# TODO(D-阶段3)：在 Worker 实现及正式模型准备完成后启动；输入为已配置的 MySQL、SummaryPipeline 和 pending 新闻，输出为持久化的摘要任务结果，必须遵守 backend/app/worker.py 与 docs/DATABASE.md。
Push-Location $BackendDirectory
python -m app.worker
Pop-Location
