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

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
# 必须使用项目统一虚拟环境解释器，裸 python 会命中系统环境导致 ImportError。
# 正式环境由 scripts/setup_runtime_env.ps1 创建于仓库根 <repo>\.venv；
# 过渡期兼容历史 backend\.venv（全局环境同步完成前允许回退）。
$PythonCandidates = @(
    (Join-Path $RepoRoot ".venv\Scripts\python.exe"),
    (Join-Path $RepoRoot "backend\.venv\Scripts\python.exe")
)
$Python = $PythonCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $Python) {
    Write-Error "未找到统一运行环境解释器（候选：$($PythonCandidates -join '；')）。请先运行 scripts\setup_runtime_env.ps1 初始化根目录 .venv"
    exit 1
}

$BackendDirectory = Join-Path $RepoRoot "backend"
if (-not (Test-Path $BackendDirectory)) {
    Write-Error "未找到后端目录：$BackendDirectory"
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
