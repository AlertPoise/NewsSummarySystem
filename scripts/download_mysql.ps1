# ============================================================================
# download_mysql.ps1 - 自动下载并解压 MySQL 8.0 免安装版（ZIP）
#
# 用途：为没有装 MySQL 的成员，一键下载到 runtime/mysql/ 并解压，不污染系统目录。
#       下载完成后仍需自行初始化（mysqld --initialize-insecure）并启动服务，
#       详见 docs/WINDOWS_SETUP.md。
#
# 默认版本：8.0.45（与项目 A 本机一致，CHECK 约束需 8.0.16+）
# 镜像源  ：清华 TUNA（国内快）；失败自动回退官方 CDN
#
# 用法：
#   powershell -ExecutionPolicy Bypass -File scripts\download_mysql.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\download_mysql.ps1 -Version 8.0.45 -Force
#
# 参数：
#   -Version      下载的 MySQL 版本号（默认 8.0.45）
#   -OutDir       解压目标目录（默认 runtime/mysql）
#   -SkipDownload 跳过下载，仅校验已存在文件
#   -Force        存在同名目录时强制重新下载
# ============================================================================

param(
    [string]$Version = '8.0.45',
    [string]$OutDir = '',
    [switch]$SkipDownload,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'

# 控制台与输出编码统一 UTF-8，避免中文/进度显示乱码
$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$PSDefaultParameterValues['Out-File:Encoding'] = 'utf8'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir

if (-not $OutDir) {
    $OutDir = Join-Path $repoRoot 'runtime\mysql'
}

# ---------------------------------------------------------------------------
# 下载源：清华 TUNA 优先，官方 CDN 兜底
# ---------------------------------------------------------------------------
$tunaBase = "https://mirrors.tuna.tsinghua.edu.cn/mysql/downloads/MySQL-8.0"
$officialBase = "https://cdn.mysql.com//Downloads/MySQL-8.0"

# 包名形如 mysql-8.0.45-winx64.zip
$zipName = "mysql-$Version-winx64.zip"
$unzipDirName = "mysql-$Version-winx64"

# 大版本段用于官方 URL（8.0.45 -> 8.0）
$majorMinor = ($Version -split '\.')[0..1] -join '.'

$urls = @(
    "$tunaBase/$zipName",
    "$officialBase/$zipName"
)

# ---------------------------------------------------------------------------
# 1. 准备目录
# ---------------------------------------------------------------------------
if (-not (Test-Path $OutDir)) {
    New-Item -ItemType Directory -Path $OutDir -Force | Out-Null
}
$zipPath = Join-Path $OutDir $zipName
$unzipTarget = Join-Path $OutDir $unzipDirName

Write-Host '=======================================================' -ForegroundColor Cyan
Write-Host ('  MySQL ' + $Version + ' 免安装版自动下载') -ForegroundColor Cyan
Write-Host '=======================================================' -ForegroundColor Cyan
Write-Host ('  目标目录 : ' + $OutDir)
Write-Host ('  压缩包   : ' + $zipName)
Write-Host ''

# ---------------------------------------------------------------------------
# 2. 若已解压且非 -Force，直接复用
# ---------------------------------------------------------------------------
if ((Test-Path (Join-Path $unzipTarget 'bin\mysqld.exe')) -and -not $Force) {
    Write-Host ('[跳过] 已存在 ' + $unzipTarget + '\bin\mysqld.exe，无需重复下载。') -ForegroundColor Green
    Write-Host ('       如需重新下载，请加 -Force。')
    exit 0
}

if ($Force) {
    if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
    if (Test-Path $unzipTarget) { Remove-Item $unzipTarget -Recurse -Force }
}

# ---------------------------------------------------------------------------
# 3. 下载（若压缩包不存在）
# ---------------------------------------------------------------------------
if (-not (Test-Path $zipPath) -or $SkipDownload -eq $false) {
    if (-not (Test-Path $zipPath)) {
        Write-Host '[下载] 开始下载 MySQL ZIP ...' -ForegroundColor Cyan
        $downloaded = $false
        foreach ($url in $urls) {
            Write-Host ('  尝试源: ' + $url) -ForegroundColor DarkGray
            try {
                # TLS 1.2 强制（旧 Windows 默认可能没开，导致 CDN 握手失败）
                [System.Net.ServicePointManager]::SecurityProtocol = `
                    [System.Net.SecurityProtocolType]::Tls12 -bor `
                    [System.Net.SecurityProtocolType]::Tls11 -bor `
                    [System.Net.SecurityProtocolType]::Tls

                $ProgressPreference = 'SilentlyContinue'
                Invoke-WebRequest -Uri $url -OutFile $zipPath -UseBasicParsing -TimeoutSec 60
                if ((Test-Path $zipPath) -and ((Get-Item $zipPath).Length -gt 10MB)) {
                    $downloaded = $true
                    break
                }
            } catch {
                Write-Host ('  该源失败: ' + $_.Exception.Message) -ForegroundColor Yellow
            }
        }
        if (-not $downloaded) {
            Write-Host '[错误] 所有下载源均失败，请检查网络或改用 -Version 指定其他版本。' -ForegroundColor Red
            exit 1
        }
    } else {
        Write-Host ('[复用] 压缩包已存在: ' + $zipPath) -ForegroundColor Green
    }
}

if ($SkipDownload -and -not (Test-Path $zipPath)) {
    Write-Host ('[错误] -SkipDownload 但压缩包不存在: ' + $zipPath) -ForegroundColor Red
    exit 1
}

# ---------------------------------------------------------------------------
# 4. 校验文件大小（MySQL 8.0 ZIP 约 200-400 MB）
# ---------------------------------------------------------------------------
$sizeMB = [math]::Round((Get-Item $zipPath).Length / 1MB, 1)
Write-Host ('[校验] 压缩包大小: ' + $sizeMB + ' MB') -ForegroundColor Cyan
if ($sizeMB -lt 50) {
    Write-Host '[错误] 压缩包异常偏小，可能下载不完整，请删除后重试。' -ForegroundColor Red
    exit 1
}

# ---------------------------------------------------------------------------
# 5. 解压
# ---------------------------------------------------------------------------
Write-Host '[解压] 解压中（约 30-60 秒）...' -ForegroundColor Cyan
try {
    if (Test-Path $unzipTarget) { Remove-Item $unzipTarget -Recurse -Force }
    Expand-Archive -Path $zipPath -DestinationPath $OutDir -Force
} catch {
    Write-Host '[错误] 解压失败，可能压缩包损坏。删除后重试，或检查磁盘空间。' -ForegroundColor Red
    Write-Host ('  ' + $_.Exception.Message) -ForegroundColor Yellow
    exit 1
}

# ---------------------------------------------------------------------------
# 6. 验证 mysqld.exe 存在
# ---------------------------------------------------------------------------
$mysqldExe = Join-Path $unzipTarget 'bin\mysqld.exe'
if (Test-Path $mysqldExe) {
    Write-Host ('[完成] mysqld.exe = ' + $mysqldExe) -ForegroundColor Green
} else {
    Write-Host '[警告] 未在预期路径找到 mysqld.exe，请检查解压目录结构。' -ForegroundColor Yellow
    Write-Host ('  预期: ' + $mysqldExe)
    exit 1
}

# ---------------------------------------------------------------------------
# 连接卡 / 下一步提示
# ---------------------------------------------------------------------------
Write-Host ''
Write-Host '==================== 下载完成 ====================' -ForegroundColor Cyan
Write-Host ('  解压位置 : ' + $unzipTarget)
Write-Host '====================================================' -ForegroundColor Cyan
Write-Host ''
Write-Host '下一步（初始化并启动 MySQL，需管理员）：' -ForegroundColor Yellow
Write-Host ''
Write-Host ('  # 1. 初始化数据目录（生成 root 空密码）')
Write-Host ('  cd "' + $unzipTarget + '"')
Write-Host ('  bin\mysqld --initialize-insecure --basedir="' + $unzipTarget + '" --datadir="' + $unzipTarget + '\data"')
Write-Host ''
Write-Host ('  # 2. 安装为 Windows 服务（可选）')
Write-Host ('  bin\mysqld --install MySQL80 --basedir="' + $unzipTarget + '" --datadir="' + $unzipTarget + '\data"')
Write-Host ('  net start MySQL80')
Write-Host ''
Write-Host ('  # 3. 或前台启动（不装服务）')
Write-Host ('  bin\mysqld --console')
Write-Host ''
Write-Host ('启动后回到项目根目录执行建库：')
Write-Host ('  powershell -ExecutionPolicy Bypass -File scripts\init_database.ps1 -MySqlExe "' + $unzipTarget + '\bin\mysql.exe"')
