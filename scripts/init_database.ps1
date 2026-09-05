# ============================================================================
# init_database.ps1 - 交互式一键建库脚本（sql/init_news_summary.sql 的薄封装）
#
# 流程：定位 mysql.exe -> root 鉴权 -> 执行 DDL -> 修改 news_app 密码 -> 生成 backend/.env
# 规范：docs/DATABASE.md 第 13 节；可重复执行（DDL 全部 IF NOT EXISTS）
#
# 用法：powershell -ExecutionPolicy Bypass -File scripts\init_database.ps1
# ============================================================================

param(
    [string]$MySqlExe = '',
    [string]$DbHost = '127.0.0.1',
    [int]$DbPort = 3306,
    [string]$DbName = 'news_summary',
    [string]$AppUser = 'news_app'
)

$ErrorActionPreference = 'Stop'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
$sqlPath = Join-Path $repoRoot 'sql\init_news_summary.sql'
$envExample = Join-Path $repoRoot 'backend\.env.example'
$envTarget = Join-Path $repoRoot 'backend\.env'

# ---------------------------------------------------------------------------
# 1. 定位 mysql.exe：参数 > PATH > 常见安装目录
# ---------------------------------------------------------------------------

function Find-MySqlExe {
    param([string]$Hint)

    if ($Hint -and (Test-Path $Hint)) { return (Resolve-Path $Hint).Path }

    $cmd = Get-Command mysql -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }

    $candidates = @(
        'F:\mysql-8.0.45-winx64\bin\mysql.exe',
        'C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe',
        'C:\Program Files\MySQL\MySQL Server 8.4\bin\mysql.exe',
        'C:\xampp\mysql\bin\mysql.exe'
    )
    foreach ($p in $candidates) {
        if (Test-Path $p) { return $p }
    }
    return $null
}

$mysql = Find-MySqlExe -Hint $MySqlExe
if (-not $mysql) {
    Write-Host '[错误] 未找到 mysql.exe。请用 -MySqlExe 参数指定完整路径。' -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $sqlPath)) {
    Write-Host ('[错误] 未找到 SQL 文件: ' + $sqlPath) -ForegroundColor Red
    exit 1
}
Write-Host ('[1/5] mysql.exe = ' + $mysql) -ForegroundColor Cyan

# ---------------------------------------------------------------------------
# 2. root 鉴权（密码经环境变量 MYSQL_PWD 传递，不落在命令行）
# ---------------------------------------------------------------------------

$rootPwd = Read-Host '请输入 MySQL root 密码（不会回显）' -AsSecureString
$rootPwdPlain = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [Runtime.InteropServices.Marshal]::SecureStringToBSTR($rootPwd))

$env:MYSQL_PWD = $rootPwdPlain
try {
    $sqlSource = $sqlPath.Replace('\', '/')
    $commonArgs = @(
        '-h', $DbHost, '-P', "$DbPort",
        '-u', 'root', '--default-character-set=utf8mb4'
    )

    Write-Host '[2/5] 验证 root 连接 ...' -ForegroundColor Cyan
    $null = & $mysql @commonArgs '-N' '-B' '-e' 'SELECT VERSION();' 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host '[错误] root 鉴权失败，请检查密码。' -ForegroundColor Red
        exit 1
    }

    # 3. 执行 DDL（含建库/建用户/授权/4 张表 + 自检输出）
    Write-Host '[3/5] 执行 DDL（可重复执行）...' -ForegroundColor Cyan
    & $mysql @commonArgs '-e' ('source ' + $sqlSource) 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host '[错误] DDL 执行失败，见上方 mysql 输出。' -ForegroundColor Red
        exit 1
    }

    # 4. 修改 news_app 密码
    Write-Host '[4/5] 设置应用账户密码（至少 8 位，将写入 backend/.env）...' -ForegroundColor Cyan
    $appPwd = Read-Host '请输入 news_app 新密码（不会回显）' -AsSecureString
    $appPwdPlain = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
        [Runtime.InteropServices.Marshal]::SecureStringToBSTR($appPwd))
    if ($appPwdPlain.Length -lt 8) {
        Write-Host '[错误] 密码至少 8 位。' -ForegroundColor Red
        exit 1
    }
    $pwdSql = $appPwdPlain.Replace("'", "''")
    $alterSql = "ALTER USER '{0}'@'localhost' IDENTIFIED BY '{1}'; ALTER USER '{0}'@'127.0.0.1' IDENTIFIED BY '{1}'; FLUSH PRIVILEGES;" -f $AppUser, $pwdSql
    & $mysql @commonArgs '-e' $alterSql 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host '[错误] 修改密码失败。' -ForegroundColor Red
        exit 1
    }

    # 用新密码做连通性验证
    $env:MYSQL_PWD = $appPwdPlain
    $appArgs = @(
        '-h', $DbHost, '-P', "$DbPort",
        '-u', $AppUser, '--default-character-set=utf8mb4'
    )
    $tableCount = (& $mysql @appArgs '-N' '-B' '-e' (
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='" + $DbName + "';"
    ) 2>&1 | Select-Object -Last 1)
    if ($LASTEXITCODE -ne 0 -or [string]$tableCount -ne '4') {
        Write-Host ('[警告] 应用账户验证异常（表数=' + $tableCount + '，应为 4）。') -ForegroundColor Yellow
    } else {
        Write-Host '      应用账户连接成功，4 张表就绪。' -ForegroundColor Green
    }

    # 5. 生成 backend/.env
    Write-Host '[5/5] 生成 backend/.env ...' -ForegroundColor Cyan
    if (Test-Path $envTarget) {
        $bak = $envTarget + '.bak'
        Copy-Item $envTarget $bak -Force
        Write-Host ('      已存在 .env，备份为 ' + (Split-Path -Leaf $bak)) -ForegroundColor Yellow
    }
    $envContent = [System.IO.File]::ReadAllText($envExample, [System.Text.Encoding]::UTF8)
    $envContent = $envContent.Replace('DB_PASSWORD=CHANGE_ME', 'DB_PASSWORD=' + $appPwdPlain)
    [System.IO.File]::WriteAllText($envTarget, $envContent, [System.Text.UTF8Encoding]::new($false))
    Write-Host '      backend/.env 已写入（其余 CHANGE_ME 项由 B/C 在阶段 2 填写）。' -ForegroundColor Green
}
finally {
    Remove-Item Env:\MYSQL_PWD -ErrorAction SilentlyContinue
    $rootPwdPlain = $null
    $appPwdPlain = $null
    [System.GC]::Collect()
}

# ---------------------------------------------------------------------------
# 连接卡
# ---------------------------------------------------------------------------

Write-Host ''
Write-Host '==================== 数据库就绪 ====================' -ForegroundColor Cyan
Write-Host ('  Host     : ' + $DbHost)
Write-Host ('  Port     : ' + $DbPort)
Write-Host ('  Database : ' + $DbName)
Write-Host ('  User     : ' + $AppUser)
Write-Host '  Password : 已写入 backend/.env（不入 Git）'
Write-Host '====================================================' -ForegroundColor Cyan
Write-Host '下一步：参考 docs/WINDOWS_SETUP.md 第 2-5 步启动后端。'
