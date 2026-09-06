# B2-07 完成后的单一续跑监控器：只在完整训练真实完成后依次执行 B2-08/B2-09。
param(
    [Parameter(Mandatory = $true)][int]$TrainingPid
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$RunPath = Join-Path $Root "runtime\training_runs\b2-07-20260905T091244Z-r0-full-train\run.json"

try {
    Wait-Process -Id $TrainingPid -ErrorAction SilentlyContinue
    if (-not (Test-Path -LiteralPath $RunPath)) {
        throw "未找到 B2-07 run.json，拒绝启动后续阶段。"
    }
    $Run = Get-Content -Raw -LiteralPath $RunPath | ConvertFrom-Json
    if ($Run.status -ne "completed") {
        throw "B2-07 状态为 $($Run.status)，不启动 B2-08/B2-09。"
    }
    & $Python (Join-Path $PSScriptRoot "b2_evaluate_validation.py")
    if ($LASTEXITCODE -ne 0) { throw "B2-08 失败，退出码 $LASTEXITCODE。" }
    & $Python (Join-Path $PSScriptRoot "b2_export.py")
    if ($LASTEXITCODE -ne 0) { throw "B2-09 失败，退出码 $LASTEXITCODE。" }
} catch {
    Write-Error $_
    exit 1
}
