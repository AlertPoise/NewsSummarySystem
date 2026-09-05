# run_worker.ps1：新闻后台任务调度入口（D 维护，对应 D3-12）。
# 单轮执行「启动自检 -> 采集入库 -> 摘要处理」；周期运行由外部调度重复调用本脚本
# （如 Windows 计划任务：powershell -NoProfile -ExecutionPolicy Bypass -File <本脚本路径>），
# 脚本自身不做循环。用法示例：
#   .\scripts\run_worker.ps1                        # 默认：每来源 20 篇 + 摘要批 50
#   .\scripts\run_worker.ps1 -Limit 5 -SkipSummary  # 仅采集入库
#   .\scripts\run_worker.ps1 -SkipCrawl             # 仅摘要处理

param(
    [int]$Limit = 20,               # 每个来源单轮最多采集条数
    [double]$Interval = 1.0,        # 详情页请求间隔秒数
    [int]$SummaryBatch = 50,        # 单轮最多处理摘要条数
    [switch]$SkipCrawl,             # 跳过采集入库阶段
    [switch]$SkipSummary,           # 跳过摘要处理阶段
    [double]$StaleMinutes = 10.0    # processing 滞留判定阈值（分钟）
)

$ErrorActionPreference = "Stop"
# worker 输出中文，控制台按 UTF-8 解码避免乱码
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$BackendDirectory = (Resolve-Path (Join-Path $PSScriptRoot "..\backend")).Path
# 必须使用项目虚拟环境解释器：依赖安装于 backend/.venv，
# 裸 python 会命中系统环境导致 ImportError
$Python = Join-Path $BackendDirectory ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    Write-Error "未找到后端虚拟环境解释器：$Python（请先按 README 完成后端环境初始化）"
    exit 1
}

$workerArgs = @(
    "-m", "app.worker",
    "--limit", $Limit,
    "--interval", $Interval,
    "--summary-batch", $SummaryBatch,
    "--stale-minutes", $StaleMinutes
)
if ($SkipCrawl) { $workerArgs += "--skip-crawl" }
if ($SkipSummary) { $workerArgs += "--skip-summary" }

# .env 按工作目录解析，必须先切到 backend 再启动
Push-Location $BackendDirectory
try {
    & $Python @workerArgs
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
