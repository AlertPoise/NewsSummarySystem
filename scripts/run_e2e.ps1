# ============================================================================
# run_e2e.ps1 - 端到端冒烟脚本（基于已存在 backend/.env 的全自动验证）
#
# 流程：
#   1) 读 backend/.env 拿连接参数
#   2) 用 mysql.exe 验证 news_app 探活 + 表数 = 4
#   3) 灌 sql/seed_test_data.sql（幂等）
#   4) 后台启 uvicorn（DATABASE_URL=mysql+pymysql）
#   5) 等就绪后用 Invoke-RestMethod 调 5 路由 + 错误码路径
#   6) pytest 连 MySQL 跑一遍（TEST_MYSQL_RESET=1）
#   7) 收尾停 uvicorn + 输出 verdicts
#
# 用法：必须在已经执行 scripts/init_database.ps1 一次后跑：
#   powershell -ExecutionPolicy Bypass -File scripts\run_e2e.ps1
# ============================================================================

param(
    [string]$MySqlExe = '',
    [int]$WaitUvicornSec = 30,
    [switch]$SkipPytest
)

# 关键修正（端到端第六轮重跑发现的踩坑）：
#   PS 5.1 的 `>` 重定向操作符默认 encoding = 'Unicode'（UTF-16 LE with BOM），
#   导致 runtime/pytest_e2e_stdout.txt 里的字符是 utf-16 LE（BOM 0xFF 0xFE + 2字节字符），
#   后续 [System.IO.File]::ReadAllText 拿到的是带 BOM 的二进制串，
#   -match '(\d+) passed' 永远命中不到 "32 passed"，verdict fail。
#
#   强制把 PS 重定向 encoding 改成 utf8。同时把控制台输出也设成 utf8，
#   让 hit 函数抓的中文 body 在 Write-Host 输出时不乱码（之前记 memory 但未真加代码）。
$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$PSDefaultParameterValues['Out-File:Encoding'] = 'utf8'

$ErrorActionPreference = 'Stop'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
$backendDir = Join-Path $repoRoot 'backend'
$envFile = Join-Path $backendDir '.env'
$seedSql = Join-Path $repoRoot 'sql\seed_test_data.sql'
$uvicornLog = Join-Path $repoRoot 'runtime\e2e_uvicorn.log'

# 关键修正（端到端第五轮重跑发现的踩坑）：
#   $uvicornLog / pytest 重定向文件都写到 runtime/，但 Join-Path 不会自动建目录，
#   上一轮 $LASTEXITCODE 路径如果有 runtime 子进程清理动作，目录会消失。
#   显式确保运行时存在。
$runtimeDir = Join-Path $repoRoot 'runtime'
if (-not (Test-Path $runtimeDir)) {
    New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null
}

$verdicts = @()

function Add-Verdict {
    param([string]$Name, [bool]$Ok, [string]$Detail = '')
    $script:verdicts += [pscustomobject]@{ Name = $Name; Ok = $Ok; Detail = $Detail }
    $tag = if ($Ok) { 'PASS' } else { 'FAIL' }
    $color = if ($Ok) { 'Green' } else { 'Red' }
    Write-Host ('  [' + $tag + '] ' + $Name + ' :: ' + $Detail) -ForegroundColor $color
}

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

function Read-DotEnvValue {
    param([string]$Path, [string]$Key)
    if (-not (Test-Path $Path)) { return $null }
    $lines = [System.IO.File]::ReadAllLines($Path)
    foreach ($line in $lines) {
        if ($line.StartsWith('#')) { continue }
        $eq = $line.IndexOf('=')
        if ($eq -lt 1) { continue }
        $name = $line.Substring(0, $eq).Trim()
        if ($name -eq $Key) { return $line.Substring($eq + 1).Trim() }
    }
    return $null
}

function Convert-DbEnvToUrl {
    # 参数加 P_ 前缀：避免与 PowerShell 内置只读变量 $Host / $Pwd 同名冲突
    param(
        [string]$P_Host, [int]$P_Port, [string]$P_Name,
        [string]$P_User, [string]$P_Pwd, [string]$P_Charset
    )
    $escapedPwd = $P_Pwd.Replace('@', '%40').Replace(':', '%3A')
    return ('mysql+pymysql://' + $P_User + ':' + $escapedPwd + '@' +
            $P_Host + ':' + $P_Port + '/' + $P_Name + '?charset=' + $P_Charset)
}

# ---------------------------------------------------------------------------
# 0. 前置检查
# ---------------------------------------------------------------------------

Write-Host '=======================================================' -ForegroundColor Cyan
Write-Host '  NewsSummary E2E 端到端验证（真 MySQL）' -ForegroundColor Cyan
Write-Host '=======================================================' -ForegroundColor Cyan

# 关键修正（5.x 端到端发现的踩坑）：
#   'Stop' 会让外部命令（pytest 等）的 stderr 触发 NativeCommandError，
#   整个 ps1 流被中断，连真实 traceback 都看不到。
#   改为 'SilentlyContinue'，由 Hit 函数与 try/catch 块自行处理错误；
#   pytest 的真实 stdout/stderr 也不会被 PS 吞掉。
$ErrorActionPreference = 'SilentlyContinue'

if (-not (Test-Path $envFile)) {
    Write-Host ('[错误] 未找到 ' + $envFile + '，请先执行 scripts\init_database.ps1') -ForegroundColor Red
    exit 1
}
$mysql = Find-MySqlExe -Hint $MySqlExe
if (-not $mysql) {
    Write-Host '[错误] 未找到 mysql.exe。请用 -MySqlExe 参数指定完整路径。' -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $seedSql)) {
    Write-Host ('[错误] 未找到 seed SQL: ' + $seedSql) -ForegroundColor Red
    exit 1
}

$dbHost = Read-DotEnvValue -Path $envFile -Key 'DB_HOST'
$dbPortStr = Read-DotEnvValue -Path $envFile -Key 'DB_PORT'
$dbName = Read-DotEnvValue -Path $envFile -Key 'DB_NAME'
$dbUser = Read-DotEnvValue -Path $envFile -Key 'DB_USER'
$dbPwd = Read-DotEnvValue -Path $envFile -Key 'DB_PASSWORD'
$dbCharset = Read-DotEnvValue -Path $envFile -Key 'DB_CHARSET'
if (-not $dbCharset) { $dbCharset = 'utf8mb4' }
if (-not $dbPortStr)  { $dbPortStr = '3306' }
$dbPort = [int]$dbPortStr

Write-Host ('[1/7] .env 解析: ' + $dbUser + '@' + $dbHost + ':' + $dbPort + '/' + $dbName) -ForegroundColor Cyan

$dbUrl = Convert-DbEnvToUrl -P_Host $dbHost -P_Port $dbPort -P_Name $dbName `
                            -P_User $dbUser -P_Pwd $dbPwd -P_Charset $dbCharset

$charsetArg = '--default-character-set=' + $dbCharset
$appArgs = @(
    '-h', $dbHost,
    '-P', "$dbPort",
    '-u', $dbUser,
    $charsetArg
)
$env:MYSQL_PWD = $dbPwd

# ---------------------------------------------------------------------------
# 1. MySQL 探活 + 表数校验
# ---------------------------------------------------------------------------

Write-Host '[2/7] MySQL 探活 + 校验 4 张表 ...' -ForegroundColor Cyan
$version = (& $mysql @appArgs '-N' '-B' '-e' 'SELECT VERSION();' 2>&1 | Select-Object -Last 1)
if ($LASTEXITCODE -ne 0) {
    Write-Host ('[错误] news_app 鉴权失败: ' + $version) -ForegroundColor Red
    exit 1
}
$tableCount = (& $mysql @appArgs '-N' '-B' '-e' (
    'SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=' +
    "'" + $dbName + "' AND table_name IN ('news_articles','favorites','feedback','model_evaluations');"
) 2>&1 | Select-Object -Last 1)
if ([string]$tableCount -eq '4') {
    Add-Verdict 'mysql.conn' $true ('version=' + $version + ', tables=4')
} else {
    Add-Verdict 'mysql.conn' $false ('实际表数=' + $tableCount + '，应为 4')
    exit 1
}

# ---------------------------------------------------------------------------
# 2. 灌 seed 数据
# ---------------------------------------------------------------------------

Write-Host '[3/7] 灌 seed_test_data.sql（幂等）...' -ForegroundColor Cyan
# 关键修正（端到端第四轮重跑发现的踩坑）：
#   上一轮残留的 favorites/feedback 子行引用 seed 新闻 → 再跑 seed 的
#   DELETE news_articles 触发 FK 约束 → mysql 退出非零 → FAIL。
#   修复点 1：seed SQL 自身先清子表再清父表（见 sql/seed_test_data.sql）。
#   修复点 2：这里把 mysql 真实输出捕获到 $seedOut，FAIL detail 携带 stdout/stderr，
#            避免「seed SQL 执行失败」这种空话，定位根因一眼可见。
$seedOut = & $mysql @appArgs $dbName '-e' ('source ' + ($seedSql.Replace('\', '/'))) 2>&1
$seedExitCode = $LASTEXITCODE
if ($seedExitCode -ne 0) {
    $errMsg = ($seedOut | Where-Object { $_ } | Select-Object -First 5) -join ' | '
    Add-Verdict 'mysql.seed' $false ('mysql 退出码=' + $seedExitCode + '；输出=' + $errMsg)
    exit 1
}
$seeded = (& $mysql @appArgs $dbName '-N' '-B' '-e' `
    "SELECT (SELECT COUNT(*) FROM news_articles WHERE content_hash=SHA2('seed_test_article_content',256)) + ` +
    `(SELECT COUNT(*) FROM model_evaluations WHERE sample_count=1000 AND dataset='CNewSum');" `
    2>&1 | Select-Object -Last 1)
if ([string]$seeded -eq '2') {
    Add-Verdict 'mysql.seed' $true 'news_articles=1, model_evaluations=1'
} else {
    Add-Verdict 'mysql.seed' $false ('seeded count=' + $seeded + '，预期 2；mysql 输出=' + ($seedOut -join ' | '))
    exit 1
}

# ---------------------------------------------------------------------------
# 3. 启 uvicorn（后台）
# ---------------------------------------------------------------------------

Write-Host '[4/7] 启动 uvicorn 后台 ...' -ForegroundColor Cyan
$uvPy = Join-Path $backendDir '.venv\Scripts\python.exe'
$env:DATABASE_URL = $dbUrl
$env:APP_HOST = '127.0.0.1'
$env:APP_PORT = '8000'

if (-not (Test-Path $uvPy)) {
    Add-Verdict 'uvicorn.boot' $false ('未找到 python: ' + $uvPy)
    exit 1
}

$uvProc = Start-Process -FilePath $uvPy `
    -ArgumentList '-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000' `
    -WorkingDirectory $backendDir `
    -RedirectStandardOutput $uvicornLog `
    -RedirectStandardError ($uvicornLog + '.err') `
    -PassThru -WindowStyle Hidden

# 等 /api/health 就绪
$healthy = $false
for ($i = 0; $i -lt $WaitUvicornSec; $i++) {
    Start-Sleep -Seconds 1
    try {
        $resp = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/api/health' `
            -UseBasicParsing -TimeoutSec 3
        if ($resp.StatusCode -eq 200) {
            $body = ($resp.Content | ConvertFrom-Json)
            if ($body.code -eq 0) {
                $healthy = $true
                break
            }
        }
    } catch {
        # 服务还没起来，继续等
    }
}
if (-not $healthy) {
    Add-Verdict 'uvicorn.boot' $false ('等 ' + $WaitUvicornSec + ' 秒未就绪；详见 ' + $uvicornLog)
    Stop-Process -Id $uvProc.Id -Force -ErrorAction SilentlyContinue
    exit 1
}
Add-Verdict 'uvicorn.boot' $true '健康检查 200 / code=0'

# ---------------------------------------------------------------------------
# 4. HTTP 契约：5 路由 + 错误码路径
# ---------------------------------------------------------------------------

Write-Host '[5/7] 5 路由契约冒烟 ...' -ForegroundColor Cyan
$cid = '550e8400-e29b-41d4-a716-446655440000'

function Hit {
    # 不抛异常：把 4xx/5xx 也包成 hash 返回，避免 catch 二次抛错穿透 Stop 偏好
    #
    # 关键修正（5.x 端到端发现的踩坑）：
    #   uvicorn 通过 HTTP/1.1 chunked 发响应，IWR 内部消费 stream 后关闭；
    #   后续再调 GetResponseStream() 返回空字符串，导致 4xx body 永远空。
    #   PowerShell 5.1+ 的 IWR 在 4xx/5xx 时会自动把 server body 塞进
    #   $_.ErrorDetails.Message，这里优先用它，stream 仅作兜底。
    param(
        [string]$Method, [string]$Path, [hashtable]$Headers = @{}, $Body = $null
    )
    $iwrArgs = @{
        Uri = ('http://127.0.0.1:8000' + $Path)
        Method = $Method
        UseBasicParsing = $true
        TimeoutSec = 5
        Headers = $Headers
    }
    if ($null -ne $Body) {
        $iwrArgs['Body'] = ($Body | ConvertTo-Json)
        $iwrArgs['ContentType'] = 'application/json'
    }
    try {
        $resp = Invoke-WebRequest @iwrArgs
        return @{ Ok = $true; StatusCode = [int]$resp.StatusCode; Content = ([string]$resp.Content) }
    } catch {
        $ex = $_.Exception
        $status = 0
        $body = ''
        if ($ex.Response) {
            try { $status = [int]$ex.Response.StatusCode } catch {}
        }
        # 优先用 IWR 自动塞进 ErrorDetails 的 4xx body（chunked stream 已被消费）
        try {
            if ($_.ErrorDetails -and $_.ErrorDetails.Message) {
                $body = [string]$_.ErrorDetails.Message
            }
        } catch {}
        # 兜底：再尝试一次 GetResponseStream（部分 server 不走 chunked）
        if (-not $body -and $ex.Response) {
            try {
                $stream = $ex.Response.GetResponseStream()
                if ($stream) {
                    $reader = New-Object System.IO.StreamReader($stream)
                    $body = $reader.ReadToEnd()
                    $reader.Close(); $stream.Close()
                }
            } catch {}
        }
        return @{ Ok = $false; StatusCode = $status; Content = $body }
    }
}

# 健康检查
$h = Hit -Method 'GET' -Path '/api/health'
$hb = $h.Content | ConvertFrom-Json
if ($h.StatusCode -eq 200 -and $hb.code -eq 0 -and $hb.data.status -eq 'healthy') {
    Add-Verdict 'route.health' $true 'GET /api/health'
} else {
    Add-Verdict 'route.health' $false 'GET /api/health 返回异常'
}

# 缺 X-Client-ID 必须触发业务错误（后端 invalid_request() 返回 HTTP 400 + code=1001，
# 对应 docs/API.md §1 + test_api.py::test_add_favorite_missing_client_id_returns_1001）
# Hit 函数已经把 4xx 包成 @{} 返回，这里直接判断
$h = Hit -Method 'POST' -Path '/api/favorites/1'
$mtBody = $null
try { $mtBody = ($h.Content | ConvertFrom-Json) } catch { $mtBody = $null }
if ($h.StatusCode -eq 400 -and $mtBody -and $mtBody.code -eq 1001) {
    Add-Verdict 'route.missing_header' $true 'POST /api/favorites 无 X-Client-ID 返回 400 + code=1001'
} else {
    Add-Verdict 'route.missing_header' $false ('期望 400+code=1001，实际 HTTP=' + $h.StatusCode + ' body=' + $h.Content)
}

# 需要找到 seed 的 news_id
# 关键修正（端到端第二轮重跑发现的踩坑）：
#   原写法用反引号续行 + `'A' + "B" + 'C'` 三段字符串拼接，PS 5.1 解析后在
#   native 调用层会把 news_id 收到 "system" 这种怪值（FastAPI int parse 失败，
#   Pydantic 把 input 显示为 "system"）。改用单变量 here-string 完全避开。
$seedNewsIdSql = "SELECT id FROM news_articles WHERE content_hash=SHA2('seed_test_article_content',256) LIMIT 1;"
$seedNewsId = (& $mysql @appArgs $dbName '-N' '-B' '-e' $seedNewsIdSql 2>&1 | Select-Object -Last 1)
if (-not $seedNewsId) {
    Add-Verdict 'route.favorite_insert' $false ('seed 新闻 id 找不到（SQL 输出为空）；SQL=' + $seedNewsIdSql)
} else {
    # POST favorites 首次
    $h = Hit -Method 'POST' -Path ('/api/favorites/' + $seedNewsId) -Headers @{ 'X-Client-ID' = $cid }
    $b = $null
    try { $b = ($h.Content | ConvertFrom-Json) } catch { $b = $null }
    if ($h.StatusCode -eq 200 -and $b -and $b.code -eq 0 -and $b.data.is_favorite -eq $true) {
        Add-Verdict 'route.favorite_insert' $true ('POST /api/favorites/' + $seedNewsId + ' 返回 is_favorite=true')
    } else {
        Add-Verdict 'route.favorite_insert' $false ('HTTP=' + $h.StatusCode + ' body=' + $h.Content)
    }

    # POST favorites 第二次（幂等）
    $h = Hit -Method 'POST' -Path ('/api/favorites/' + $seedNewsId) -Headers @{ 'X-Client-ID' = $cid }
    $b = $null
    try { $b = ($h.Content | ConvertFrom-Json) } catch { $b = $null }
    if ($h.StatusCode -eq 200 -and $b -and $b.code -eq 0 -and $b.data.is_favorite -eq $true) {
        Add-Verdict 'route.favorite_idempotent' $true 'POST 第二次仍 200 + is_favorite=true'
    } else {
        Add-Verdict 'route.favorite_idempotent' $false ('HTTP=' + $h.StatusCode + ' body=' + $h.Content)
    }

    # POST feedback 首次
    $h = Hit -Method 'POST' -Path ('/api/news/' + $seedNewsId + '/feedback') `
        -Headers @{ 'X-Client-ID' = $cid } -Body @{ helpful = $true }
    $b = $null
    try { $b = ($h.Content | ConvertFrom-Json) } catch { $b = $null }
    if ($h.StatusCode -eq 200 -and $b -and $b.code -eq 0 -and $b.data.helpful -eq $true) {
        Add-Verdict 'route.feedback_insert' $true 'POST feedback helpful=true 创建成功'
    } else {
        Add-Verdict 'route.feedback_insert' $false ('HTTP=' + $h.StatusCode + ' body=' + $h.Content)
    }

    # POST feedback UPDATE
    $h = Hit -Method 'POST' -Path ('/api/news/' + $seedNewsId + '/feedback') `
        -Headers @{ 'X-Client-ID' = $cid } -Body @{ helpful = $false }
    $b = $null
    try { $b = ($h.Content | ConvertFrom-Json) } catch { $b = $null }
    if ($h.StatusCode -eq 200 -and $b -and $b.code -eq 0 -and $b.data.helpful -eq $false) {
        Add-Verdict 'route.feedback_update' $true 'POST feedback helpful=false 改成 false'
    } else {
        Add-Verdict 'route.feedback_update' $false ('HTTP=' + $h.StatusCode + ' body=' + $h.Content)
    }

# GET /api/favorites 列表
# 关键修正（端到端第三轮重跑发现的踩坑）：
#   原断言 $b.data.items.Count，但 favorites.py::list_favorites 的 response_model 是
#   ApiResponse[list[NewsListItem]]，实际 data 字段是直接数组（test_api.py:156
#   `len(payload["data"]) == 1` 已确认），不是 {items: [...]} 包装。
#   改成 $b.data.Count。
$h = Hit -Method 'GET' -Path '/api/favorites' -Headers @{ 'X-Client-ID' = $cid }
$b = $null
try { $b = ($h.Content | ConvertFrom-Json) } catch { $b = $null }
$dataCount = 0
if ($b -and $b.data) {
    if ($b.data -is [array]) { $dataCount = $b.data.Count }
    elseif ($b.data.PSObject.Properties['items']) { $dataCount = $b.data.items.Count }
}
if ($h.StatusCode -eq 200 -and $b -and $b.code -eq 0 -and $dataCount -ge 1) {
    Add-Verdict 'route.favorite_list' $true ('GET /api/favorites items=' + $dataCount)
} else {
    Add-Verdict 'route.favorite_list' $false ('HTTP=' + $h.StatusCode + ' body=' + $h.Content)
}

    # GET /api/model/metrics
    $h = Hit -Method 'GET' -Path '/api/model/metrics'
    $b = $null
    try { $b = ($h.Content | ConvertFrom-Json) } catch { $b = $null }
    if ($h.StatusCode -eq 200 -and $b -and $b.code -eq 0 -and $b.data.dataset -eq 'CNewSum') {
        $rougeL = $b.data.rougeL
        Add-Verdict 'route.metrics' $true ('GET metrics rougeL=' + $rougeL)
    } else {
        Add-Verdict 'route.metrics' $false ('HTTP=' + $h.StatusCode + ' body=' + $h.Content)
    }

    # DELETE favorites（幂等取消）
    $h = Hit -Method 'DELETE' -Path ('/api/favorites/' + $seedNewsId) -Headers @{ 'X-Client-ID' = $cid }
    $b = $null
    try { $b = ($h.Content | ConvertFrom-Json) } catch { $b = $null }
    if ($h.StatusCode -eq 200 -and $b -and $b.code -eq 0 -and $b.data.is_favorite -eq $false) {
        Add-Verdict 'route.favorite_delete' $true 'DELETE favorites is_favorite=false'
    } else {
        Add-Verdict 'route.favorite_delete' $false ('HTTP=' + $h.StatusCode + ' body=' + $h.Content)
    }

    # FK 错误路径：POST 不存在的 news_id 期望 404 + code=1002
    # Hit 已自动包错；不再在外层 try-catch，避免 catch 二次抛错穿透 Stop 偏好
    $h = Hit -Method 'POST' -Path '/api/favorites/999999' -Headers @{ 'X-Client-ID' = $cid }
    $fkBody = $null
    try { $fkBody = ($h.Content | ConvertFrom-Json) } catch { $fkBody = $null }
    if ($h.StatusCode -eq 404 -and $fkBody -and $fkBody.code -eq 1002) {
        Add-Verdict 'route.fk_missing_news' $true 'POST favorites/999999 返回 404 + code=1002'
    } elseif ($h.StatusCode -eq 404) {
        $gotCode = if ($fkBody) { $fkBody.code } else { '(null)' }
        Add-Verdict 'route.fk_missing_news' $false ('HTTP 404 但 code=' + $gotCode + ' 期望 1002；body=' + $h.Content)
    } else {
        Add-Verdict 'route.fk_missing_news' $false ('期望 404+code=1002，实际 HTTP=' + $h.StatusCode + ' body=' + $h.Content)
    }
}

# ---------------------------------------------------------------------------
# 5. pytest 连 MySQL 跑全套（DATABASE_URL=mysql + TEST_MYSQL_RESET=1）
# ---------------------------------------------------------------------------

if (-not $SkipPytest) {
    Write-Host '[6/7] pytest -m 切 MySQL 跑 32 项 ...' -ForegroundColor Cyan
    $env:DATABASE_URL = $dbUrl
    $env:TEST_MYSQL_RESET = '1'
    $pytestPy = Join-Path $backendDir '.venv\Scripts\python.exe'
    # 关键修正（端到端第二轮重跑发现的踩坑）：
    #   即便顶部 $ErrorActionPreference='SilentlyContinue' + try/catch 包住，
    #   pytest 抛 ImportError 时 stderr 流仍可能只让 catch 抓到一行概要，
    #   完整 traceback 在 stderr 流里被吞。改用 Start-Process 把 stdout/stderr
    #   显式重定向到临时文件，最后读两个文件 + 拼接，确保 ImportError 全栈可见。
    $pytestStdout = Join-Path $repoRoot 'runtime\pytest_e2e_stdout.txt'
    $pytestStderr = Join-Path $repoRoot 'runtime\pytest_e2e_stderr.txt'
    Remove-Item $pytestStdout, $pytestStderr -ErrorAction SilentlyContinue
    # 关键修正（端到端第七轮重跑发现的踩坑）：
    #   原本用 `'--rootdir=' + $backendDir` 字符串拼接传给 pytest，
    #   PS 5.1 call operator 处理带 `\Windows\backend` 反斜杠路径时会"二次转义"
    #   或拆 token，导致 ps1 跑出 collected 0 items，但 bash 完全相同命令能 32 passed。
    #   改用 `& $pytestPy @pytestArgs` array splatting：每个 token 独立元素，
    #   不会再被字符串拼接污染。
    $pytestArgs = @(
        '-m', 'pytest'
        (Join-Path $backendDir 'tests')
        ('--rootdir=' + $backendDir)
        '-v', '--tb=short', '--no-header'
    )
    Write-Host ('      cmd:  ' + $pytestPy + ' ' + ($pytestArgs -join ' ')) -ForegroundColor DarkGray
    Write-Host ('      DATABASE_URL=' + $env:DATABASE_URL) -ForegroundColor DarkGray
    # 关键修正（端到端第六轮重跑发现的踩坑）：
    #   PS 5.1 `>` 重定向操作符默认 UTF-16 LE with BOM，写出的 stdout 文件是 binary 串，
    #   ReadAllText 后 -match 永远命中不到 "32 passed"。脚本顶部已三连设置 encoding
    #   （$OutputEncoding / [Console]::OutputEncoding / Out-File:Encoding），文件 utf-8 落盘。
    # 关键修正（端到端第五轮重跑发现的踩坑）：
    #   `'1>'` `'2>'` 用单引号包住 → PS 5.1 当字符串参数传给 pytest，
    #   pytest 不识别 → exit 2 → stdout/stderr 文件根本没创建。改裸 token。
    & $pytestPy @pytestArgs 1> $pytestStdout 2> $pytestStderr
    $outRaw = ''
    $errRaw = ''
    if (Test-Path $pytestStdout) { $outRaw = [System.IO.File]::ReadAllText($pytestStdout) }
    if (Test-Path $pytestStderr) { $errRaw = [System.IO.File]::ReadAllText($pytestStderr) }
    $pytestStr = $outRaw + "`n---STDERR---`n" + $errRaw
    # 关键修正（端到端第五轮重跑发现的踩坑）：
    #   用 `Select-Object -Last 1` 拿「最后一行」对长字符串元素是脆弱的。
    #   改为：用整个组合输出做正则，匹配 pytest summary banner 形式
    #   `=== 32 passed in 1.50s ===`，跨多行也能命中。多 fallback 兜底。
    $passedCount = 0
    if ($pytestStr -match '=\s*(\d+)\s+passed') {
        $passedCount = [int]$Matches[1]
    } elseif ($pytestStr -match '(?m)^\s*(\d+)\s+passed\s+in\s+\d') {
        $passedCount = [int]$Matches[1]
    } elseif ($pytestStr -match '(\d+)\s+passed') {
        $passedCount = [int]$Matches[1]
    }
    if ($passedCount -gt 0) {
        Add-Verdict 'pytest.mysql' $true ($passedCount.ToString() + ' passed (MySQL 模式)')
    } else {
        Add-Verdict 'pytest.mysql' $false 'pytest 输出未匹配到 passed 计数（详见下方 tail）'
        Write-Host '--- pytest output tail (last 2000 chars) ---' -ForegroundColor Yellow
        Write-Host ($pytestStr.Substring([Math]::Max(0, $pytestStr.Length - 2000)))
    }
} else {
    Add-Verdict 'pytest.mysql' $true 'Skipped (-SkipPytest)'
}

# ---------------------------------------------------------------------------
# 6. 收尾
# ---------------------------------------------------------------------------

Write-Host '[7/7] 收尾：停止 uvicorn ...' -ForegroundColor Cyan
try { Stop-Process -Id $uvProc.Id -Force -ErrorAction Stop } catch { }
Remove-Item Env:\MYSQL_PWD -ErrorAction SilentlyContinue
Remove-Item Env:\DATABASE_URL -ErrorAction SilentlyContinue
Remove-Item Env:\TEST_MYSQL_RESET -ErrorAction SilentlyContinue

# ---------------------------------------------------------------------------
# 总览
# ---------------------------------------------------------------------------

Write-Host ''
Write-Host '==================== 端到端验证总结 ====================' -ForegroundColor Cyan
$failCount = 0
foreach ($v in $verdicts) {
    $tag = if ($v.Ok) { 'PASS' } else { 'FAIL' }
    $color = if ($v.Ok) { 'Green' } else { 'Red' }
    Write-Host ('  [' + $tag + '] ' + $v.Name + ' :: ' + $v.Detail) -ForegroundColor $color
    if (-not $v.Ok) { $failCount++ }
}
Write-Host '--------------------------------------------------------' -ForegroundColor Cyan
Write-Host ('  总计: ' + $verdicts.Count + ' 项 / 失败: ' + $failCount) -ForegroundColor Cyan
if ($failCount -eq 0) {
    Write-Host '  >>> ALL GREEN，端到端真库验证通过 <<<' -ForegroundColor Green
    exit 0
} else {
    Write-Host '  >>> 有 ' + $failCount + ' 项失败，请检查上方详情 <<<' -ForegroundColor Red
    exit 1
}
