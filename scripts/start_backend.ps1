$BackendDirectory = Join-Path $PSScriptRoot "..\backend"

# TODO(A-阶段1)：由 A 在完成 backend/.env 本机配置后运行；输入为已激活的 Python 3.11 虚拟环境和依赖，输出为监听 APP_HOST:APP_PORT 的 FastAPI 进程，必须遵守 docs/WINDOWS_SETUP.md。
Push-Location $BackendDirectory
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
Pop-Location
