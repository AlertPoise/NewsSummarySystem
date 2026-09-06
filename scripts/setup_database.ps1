# ============================================================================
# setup_database.ps1 - Windows 上的 NewsSummarySystem 数据库首次部署入口
# 只负责准备/启动既有 MySQL Server，并委托 init_database.ps1 建库。
# ============================================================================

param([switch]$Elevated)

$ErrorActionPreference = 'Stop'
$scriptPath = $MyInvocation.MyCommand.Path
$scriptDir = Split-Path -Parent $scriptPath
$repoRoot = Split-Path -Parent $scriptDir
$minimumVersion = [version]'8.0.16'
$runtimeDir = Join-Path $repoRoot 'runtime'
$setupLog = Join-Path $runtimeDir 'setup_database_admin.log'

function Write-SetupLog {
    param([string]$Message)
    if (-not (Test-Path $runtimeDir)) { New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null }
    $line = ('{0} {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Message)
    [IO.File]::AppendAllText($setupLog, $line + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))
}

function Write-StepResult {
    param([string]$Step, [string]$Status, [string]$Message)
    $color = if ($Status -eq 'PASS') { 'Green' } elseif ($Status -eq 'FAIL') { 'Red' } else { 'Yellow' }
    Write-Host ("[{0}] {1}" -f $Step, $Message) -ForegroundColor $color
    Write-SetupLog ("[$Step][$Status] $Message")
}

function Get-ExecutableFromServicePath {
    param([string]$PathName)
    if ([string]::IsNullOrWhiteSpace($PathName)) { return $null }
    $match = [regex]::Match($PathName, '^\s*"(?<path>[^"]+\.exe)"|^\s*(?<path>[^\s]+\.exe)', 'IgnoreCase')
    if ($match.Success) { return $match.Groups['path'].Value }
    return $null
}

function Get-MySqlServices {
    $services = @(Get-CimInstance -ClassName Win32_Service -ErrorAction Stop | Where-Object {
        $_.Name -match '(?i)mysql' -or $_.DisplayName -match '(?i)mysql' -or $_.PathName -match '(?i)mysqld(?:\.exe)?'
    })
    foreach ($service in $services) {
        $serverPath = Get-ExecutableFromServicePath $service.PathName
        [pscustomobject]@{
            Name = $service.Name; DisplayName = $service.DisplayName; State = $service.State
            PathName = $service.PathName; ServerPath = $serverPath
        }
    }
}

function Find-MySqlServerBinaries {
    $found = New-Object System.Collections.Generic.List[string]
    $command = Get-Command mysqld -ErrorAction SilentlyContinue
    if ($command -and (Test-Path $command.Source)) { $found.Add($command.Source) }
    $roots = @(
        (Join-Path ${env:ProgramFiles} 'MySQL'),
        (Join-Path ${env:ProgramFiles(x86)} 'MySQL'),
        'C:\xampp\mysql', 'C:\mysql'
    ) | Where-Object { $_ -and (Test-Path $_) }
    foreach ($root in $roots) {
        Get-ChildItem -Path $root -Filter 'mysqld.exe' -File -Recurse -ErrorAction SilentlyContinue |
            ForEach-Object { $found.Add($_.FullName) }
    }
    return @($found | Select-Object -Unique)
}

function Find-MySqlClient {
    param([string]$ServerPath)
    if ($ServerPath) {
        $nearby = Join-Path (Split-Path -Parent $ServerPath) 'mysql.exe'
        if (Test-Path $nearby) { return (Resolve-Path $nearby).Path }
    }
    $command = Get-Command mysql -ErrorAction SilentlyContinue
    if ($command -and (Test-Path $command.Source)) { return $command.Source }
    foreach ($server in (Find-MySqlServerBinaries)) {
        $nearby = Join-Path (Split-Path -Parent $server) 'mysql.exe'
        if (Test-Path $nearby) { return $nearby }
    }
    return $null
}

function Test-IsAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Invoke-ElevatedSelf {
    if (Test-IsAdministrator) { return $false }
    if ($Elevated) { throw '管理员进程未获得提升权限。请在 UAC 提示中选择“是”后重新运行。' }
    Write-Host '需要管理员权限，将请求 UAC 并在提升后的 PowerShell 中继续。' -ForegroundColor Yellow
    Write-SetupLog 'Requesting UAC elevation for setup_database.ps1.'
    $arguments = '-NoProfile -ExecutionPolicy Bypass -File "' + $scriptPath + '" -Elevated'
    try {
        $process = Start-Process -FilePath 'powershell.exe' -Verb RunAs -ArgumentList $arguments -Wait -PassThru -ErrorAction Stop
        Write-SetupLog ("Elevated process exited with code $($process.ExitCode).")
        exit $process.ExitCode
    } catch {
        throw "无法启动管理员 PowerShell。请接受 UAC 提示后重试。原因：$($_.Exception.Message)"
    }
}

function Invoke-MySqlCommandCapture {
    param([string]$MySqlExe, [string[]]$Arguments)
    $output = & $MySqlExe @Arguments 2>&1
    return [pscustomobject]@{ ExitCode = $LASTEXITCODE; Output = ($output -join "`n") }
}

function Get-RootAuthState {
    param([string]$MySqlExe)
    $result = Invoke-MySqlCommandCapture -MySqlExe $MySqlExe -Arguments @('--protocol=TCP', '-h', '127.0.0.1', '-P', '3306', '-u', 'root', '-N', '-B', '-e', 'SELECT VERSION(), CURRENT_USER();')
    if ($result.ExitCode -eq 0) { return [pscustomobject]@{ State = 'NoPassword'; Detail = 'root 无密码 TCP 登录成功。' } }
    if ($result.Output -match '(?i)(error\s+1045|access denied)') { return [pscustomobject]@{ State = 'PasswordRequired'; Detail = 'Server 在线，但 root 需要密码。' } }
    if ($result.Output -match '(?i)(can.t connect|connection refused|error\s+200[23])') { return [pscustomobject]@{ State = 'ConnectionFailed'; Detail = $result.Output } }
    return [pscustomobject]@{ State = 'Unknown'; Detail = $result.Output }
}

function Set-RootPasswordFromCurrentSession {
    param([string]$MySqlExe, [string]$CurrentPassword, [switch]$CurrentPasswordIsEmpty)
    $newPassword = Read-Host '请输入 MySQL root 新密码（不会回显）' -AsSecureString
    $newPasswordPlain = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($newPassword))
    if ([string]::IsNullOrWhiteSpace($newPasswordPlain) -or $newPasswordPlain.Length -lt 8) { throw 'root 密码至少需要 8 位。' }
    $escapedPassword = $newPasswordPlain.Replace("'", "''")
    $oldPassword = $env:MYSQL_PWD; $hadPassword = Test-Path Env:\MYSQL_PWD
    try {
        if ($CurrentPasswordIsEmpty) { Remove-Item Env:\MYSQL_PWD -ErrorAction SilentlyContinue } else { $env:MYSQL_PWD = $CurrentPassword }
        "ALTER USER 'root'@'localhost' IDENTIFIED BY '$escapedPassword'; FLUSH PRIVILEGES;" | & $MySqlExe '--protocol=TCP' '-h' '127.0.0.1' '-P' '3306' '-u' 'root' '--default-character-set=utf8mb4' 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) { throw 'root 密码设置失败（密码未输出）。' }
        $env:MYSQL_PWD = $newPasswordPlain
        $verify = Invoke-MySqlCommandCapture -MySqlExe $MySqlExe -Arguments @('--protocol=TCP', '-h', '127.0.0.1', '-P', '3306', '-u', 'root', '-N', '-B', '-e', 'SELECT 1;')
        if ($verify.ExitCode -ne 0) { throw 'root 新密码验证失败（密码未输出）。' }
    } finally {
        if ($hadPassword) { $env:MYSQL_PWD = $oldPassword } else { Remove-Item Env:\MYSQL_PWD -ErrorAction SilentlyContinue }
        $newPasswordPlain = $null; $escapedPassword = $null; [GC]::Collect()
    }
}

function Ensure-RootAuthentication {
    param([string]$MySqlExe, $ProjectInstall)
    $state = Get-RootAuthState $MySqlExe
    if ($state.State -eq 'NoPassword') {
        $saved = $null
        if ($ProjectInstall -and (Test-Path $ProjectInstall.Marker)) { $saved = Get-Content -LiteralPath $ProjectInstall.Marker -Raw | ConvertFrom-Json }
        if (-not $saved -or $saved.RootPasswordConfigured) { throw 'root 无密码登录成功，但该实例不是可确认的本项目初始状态；为保护已有实例，脚本不会重置 root 密码。' }
        Write-Host '检测到 initialize-insecure 初始状态：root 当前无密码。' -ForegroundColor Yellow
        Set-RootPasswordFromCurrentSession -MySqlExe $MySqlExe -CurrentPassword '' -CurrentPasswordIsEmpty
        if ($ProjectInstall) { Write-BootstrapMarker -Install $ProjectInstall -RootPasswordConfigured $true }
        return
    }
    if ($state.State -eq 'PasswordRequired') {
        $saved = $null
        if ($ProjectInstall -and (Test-Path $ProjectInstall.Marker)) { $saved = Get-Content -LiteralPath $ProjectInstall.Marker -Raw | ConvertFrom-Json }
        if ($saved -and -not $saved.RootPasswordConfigured) {
            $current = Read-Host '请输入错误日志中显示的临时 root 密码（不会回显）' -AsSecureString
            $currentPlain = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($current))
            try { Set-RootPasswordFromCurrentSession -MySqlExe $MySqlExe -CurrentPassword $currentPlain; Write-BootstrapMarker -Install $ProjectInstall -RootPasswordConfigured $true }
            finally { $currentPlain = $null; [GC]::Collect() }
        } else {
            $current = Read-Host '请输入现有 MySQL root 密码（不会回显，仅用于验证）' -AsSecureString
            $currentPlain = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($current))
            try {
                $oldPassword = $env:MYSQL_PWD; $hadPassword = Test-Path Env:\MYSQL_PWD; $env:MYSQL_PWD = $currentPlain
                $verify = Invoke-MySqlCommandCapture -MySqlExe $MySqlExe -Arguments @('--protocol=TCP', '-h', '127.0.0.1', '-P', '3306', '-u', 'root', '-N', '-B', '-e', 'SELECT 1;')
                if ($verify.ExitCode -ne 0) { throw 'root 密码认证失败（密码未输出）。' }
                if ($hadPassword) { $env:MYSQL_PWD = $oldPassword } else { Remove-Item Env:\MYSQL_PWD -ErrorAction SilentlyContinue }
            } finally { $currentPlain = $null; [GC]::Collect() }
        }
        return
    }
    throw ("无法安全判断 root 状态：" + $state.Detail)
}

function Get-OfficialUnconfiguredInstall {
    param([string[]]$ServerBinaries, [object[]]$Services)
    if ($Services.Count -gt 0) { return $null }
    $installCandidates = @()
    foreach ($server in $ServerBinaries) {
        $binDir = Split-Path -Parent $server
        $installRoot = Split-Path -Parent $binDir
        if ($installRoot -notmatch '(?i)^C:\\Program Files\\MySQL\\MySQL Server \d+\.\d+$') { continue }
        $serverSignature = Get-AuthenticodeSignature -FilePath $server
        if ($serverSignature.Status -ne 'Valid' -or $serverSignature.SignerCertificate.Subject -notmatch '(?i)Oracle') { continue }
        $version = Get-MySqlVersion $server
        $versionText = $version.ToString(2)
        $dataRoot = Join-Path $env:ProgramData (Join-Path 'MySQL' ("MySQL Server " + $versionText))
        $dataDirectory = Join-Path $dataRoot 'Data'
        $myIni = Join-Path $dataRoot 'my.ini'
        $marker = Join-Path $dataRoot '.news-summary-system-mysql-bootstrap.json'
        $serviceName = 'NewsSummarySystemMySQL' + $version.Major + $version.Minor
        $standardConfigs = @((Join-Path $installRoot 'my.ini'), $myIni, (Join-Path $env:WINDIR 'my.ini'), 'C:\my.ini')
        $existingConfig = @($standardConfigs | Where-Object { Test-Path $_ })
        $state = $null
        # New: no data or option file exists anywhere that this installation would read.
        if (-not (Test-Path $dataRoot) -and $existingConfig.Count -eq 0) { $state = 'New' }
        # Resume: only a marker written by this script may authorize touching a nonempty datadir.
        elseif ((Test-Path $marker) -and (Test-Path $myIni) -and (Test-Path $dataDirectory)) {
            try {
                $saved = Get-Content -LiteralPath $marker -Raw | ConvertFrom-Json
                if ($saved.ServerPath -eq $server -and $saved.ServiceName -eq $serviceName -and $saved.Version -eq $version.ToString()) { $state = 'Resume' }
            } catch { $state = $null }
        }
        if (-not $state) { continue }
        $installCandidates += [pscustomobject]@{ ServerPath = $server; Version = $version; InstallRoot = $installRoot; DataRoot = $dataRoot; DataDirectory = $dataDirectory; MyIni = $myIni; Marker = $marker; ServiceName = $serviceName; State = $state }
    }
    if ($installCandidates.Count -eq 1) { return $installCandidates[0] }
    if ($installCandidates.Count -gt 1) { throw '检测到多个未配置的 Oracle MySQL 安装，无法安全自动选择。请人工保留一个候选后重试。' }
    return $null
}

function Get-ProjectBootstrapInstall {
    param($Candidate)
    if (-not $Candidate -or -not $Candidate.Service.PathName) { return $null }
    $iniMatch = [regex]::Match($Candidate.Service.PathName, '(?i)--defaults-file=(?:"(?<path>[^"]+)"|(?<path>\S+))')
    if (-not $iniMatch.Success) { return $null }
    $myIni = $iniMatch.Groups['path'].Value
    $dataRoot = Split-Path -Parent $myIni
    $marker = Join-Path $dataRoot '.news-summary-system-mysql-bootstrap.json'
    if (-not (Test-Path $myIni) -or -not (Test-Path $marker)) { return $null }
    try {
        $saved = Get-Content -LiteralPath $marker -Raw | ConvertFrom-Json
        if ($saved.ServerPath -ne $Candidate.Service.ServerPath -or $saved.ServiceName -ne $Candidate.Service.Name -or $saved.Version -ne $Candidate.Version.ToString()) { return $null }
        $dataDirectory = Join-Path $dataRoot 'Data'
        if (-not (Test-Path $dataDirectory)) { return $null }
        return [pscustomobject]@{ ServerPath = $Candidate.Service.ServerPath; Version = $Candidate.Version; InstallRoot = Split-Path -Parent (Split-Path -Parent $Candidate.Service.ServerPath); DataRoot = $dataRoot; DataDirectory = $dataDirectory; MyIni = $myIni; Marker = $marker; ServiceName = $Candidate.Service.Name; State = 'Configured' }
    } catch { return $null }
}

function Write-BootstrapMarker {
    param($Install, [bool]$RootPasswordConfigured)
    $content = [pscustomobject]@{ ServerPath = $Install.ServerPath; Version = $Install.Version.ToString(); ServiceName = $Install.ServiceName; RootPasswordConfigured = $RootPasswordConfigured } | ConvertTo-Json
    [IO.File]::WriteAllText($Install.Marker, $content, [Text.UTF8Encoding]::new($false))
}

function Initialize-OfficialMySqlInstall {
    param($Install)
    if (-not (Test-IsAdministrator)) { throw '首次初始化、写入专属 my.ini 和注册 Windows Service 需要管理员权限。请使用“以管理员身份运行”的 PowerShell 重新执行本脚本。' }
    if ($Install.State -eq 'New') {
        if (Test-TcpPort) { throw '127.0.0.1:3306 已被占用；为避免影响未知实例，脚本不会初始化新的 MySQL 服务。' }
        New-Item -ItemType Directory -Path $Install.DataRoot -ErrorAction Stop | Out-Null
        $ini = @"
[mysqld]
basedir="$($Install.InstallRoot.Replace('\', '/'))"
datadir="$($Install.DataDirectory.Replace('\', '/'))"
port=3306
bind-address=127.0.0.1
mysqlx-port=33060
"@
        [IO.File]::WriteAllText($Install.MyIni, $ini, [Text.UTF8Encoding]::new($false))
        Write-BootstrapMarker -Install $Install -RootPasswordConfigured $false
        & $Install.ServerPath ("--defaults-file=" + $Install.MyIni) '--initialize-insecure' 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "mysqld 初始化失败（exit code $LASTEXITCODE）。保留专属配置和标记以便安全恢复；未删除任何文件。" }
    }
    $service = Get-Service -Name $Install.ServiceName -ErrorAction SilentlyContinue
    if (-not $service) {
        & $Install.ServerPath '--install' $Install.ServiceName ("--defaults-file=" + $Install.MyIni) 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Windows Service 注册失败（exit code $LASTEXITCODE）。如为 Access is denied，请使用管理员 PowerShell 重新运行。" }
    }
    $mysqlExe = Find-MySqlClient $Install.ServerPath
    if (-not $mysqlExe) { throw '初始化实例时未找到同安装目录的 mysql.exe。' }
    $bootstrapCandidate = [pscustomobject]@{ Service = [pscustomobject]@{ Name = $Install.ServiceName; State = (Get-Service -Name $Install.ServiceName).Status } }
    Start-MySqlService $bootstrapCandidate
    Wait-MySqlReady -ServiceName $Install.ServiceName -MySqlExe $mysqlExe
    Ensure-RootAuthentication -MySqlExe $mysqlExe -ProjectInstall $Install
}

function Get-MySqlVersion {
    param([string]$ServerPath)
    if (-not $ServerPath -or -not (Test-Path $ServerPath)) { return $null }
    $output = & $ServerPath '--version' 2>&1
    if ($LASTEXITCODE -ne 0) { throw "无法读取 MySQL Server 版本：$ServerPath" }
    $match = [regex]::Match(($output -join "`n"), '(?<version>\d+\.\d+\.\d+)')
    if (-not $match.Success) { throw "无法解析 MySQL Server 版本：$($output -join ' ')" }
    return [version]$match.Groups['version'].Value
}

function Get-MySqlServicePort {
    param($Service)
    $text = [string]$Service.PathName
    $match = [regex]::Match($text, '(?i)--port(?:=|\s+)(?<port>\d+)')
    if ($match.Success) { return [int]$match.Groups['port'].Value }
    $iniMatch = [regex]::Match($text, '(?i)--defaults-file(?:=|\s+)["'']?(?<path>[^"'']+?\.ini)(?:["'']|\s|$)')
    if ($iniMatch.Success -and (Test-Path $iniMatch.Groups['path'].Value)) {
        foreach ($line in Get-Content -LiteralPath $iniMatch.Groups['path'].Value -ErrorAction Stop) {
            if ($line -match '^\s*port\s*=\s*(?<port>\d+)\s*(?:#|;|$)') { return [int]$matches['port'] }
        }
    }
    # 未显式设置端口的 MySQL Windows 服务遵循 MySQL 默认端口 3306。
    return 3306
}

function Select-MySqlService {
    param([object[]]$Services)
    $candidates = @()
    foreach ($service in $Services) {
        if (-not $service.ServerPath -or -not (Test-Path $service.ServerPath)) { continue }
        $version = Get-MySqlVersion $service.ServerPath
        $candidates += [pscustomobject]@{
            Service = $service; Version = $version; Port = Get-MySqlServicePort $service
            Running = ($service.State -eq 'Running')
        }
    }
    $eligible = @($candidates | Where-Object { $_.Version -ge $minimumVersion -and $_.Port -eq 3306 })
    if ($eligible.Count -eq 0) {
        $wrongVersion = @($candidates | Where-Object { $_.Port -eq 3306 -and $_.Version -lt $minimumVersion })
        if ($wrongVersion.Count -gt 0) {
            $reported = ($wrongVersion | ForEach-Object { "$($_.Service.Name): $($_.Version)" }) -join ', '
            throw "MySQL Server 当前版本 $reported；最低版本要求为 $minimumVersion。不会自动升级现有数据库。"
        }
        return $null
    }
    $running = @($eligible | Where-Object { $_.Running })
    if ($running.Count -gt 0) { $best = @($running) } else { $best = @($eligible) }
    if ($best.Count -ne 1) {
        Write-Host '[FAIL] 检测到多个同等优先级的 MySQL 服务，无法安全自动选择：' -ForegroundColor Red
        $best | ForEach-Object { Write-Host ("  - {0} ({1}, {2}, port {3})" -f $_.Service.Name, $_.Version, $_.Service.State, $_.Port) }
        throw '请停止或移除歧义后重新运行；脚本不会随机启动多个实例。'
    }
    return $best[0]
}

function Install-MySqlServer {
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $winget) { throw '未检测到 MySQL Server，且当前系统不可用 winget，请先安装 MySQL 8.x 后重新运行本脚本。' }
    $wingetExe = $winget.Source
    & $wingetExe '--version' | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'winget 不可用，请先安装 MySQL 8.x 后重新运行本脚本。' }
    Write-Host '未检测到 MySQL Server，接下来将尝试安装，可能请求管理员权限。' -ForegroundColor Yellow
    # Oracle.MySQL 是 winget 社区源中 MySQL Server 的官方发布者包；不使用第三方下载地址。
    & $wingetExe 'install' '--id' 'Oracle.MySQL' '--exact' '--accept-package-agreements' '--accept-source-agreements'
    if ($LASTEXITCODE -ne 0) { throw "winget 安装 MySQL Server 失败（exit code $LASTEXITCODE）。" }
}

function Start-MySqlService {
    param($Candidate)
    $name = $Candidate.Service.Name
    if ($Candidate.Service.State -ne 'Running') {
        try { Start-Service -Name $name -ErrorAction Stop }
        catch { throw "未能启动 MySQL 服务 '$name'。原因：$($_.Exception.Message)。如为 Access is denied，请使用管理员 PowerShell 重新运行。" }
    }
    $current = Get-Service -Name $name -ErrorAction Stop
    if ($current.Status -ne 'Running') { throw "MySQL 服务 '$name' 未处于 Running 状态。" }
}

function Test-TcpPort {
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $async = $client.BeginConnect('127.0.0.1', 3306, $null, $null)
        if (-not $async.AsyncWaitHandle.WaitOne(1000, $false)) { $client.Close(); return $false }
        $client.EndConnect($async); $client.Close(); return $true
    } catch { return $false }
}

function Wait-MySqlReady {
    param([string]$ServiceName, [string]$MySqlExe)
    for ($second = 0; $second -lt 60; $second++) {
        $status = (Get-Service -Name $ServiceName -ErrorAction Stop).Status
        if ($status -ne 'Running') { throw "MySQL 服务 '$ServiceName' 在启动期间停止。" }
        if (Test-TcpPort) {
            # TCP 加上已验证的 mysqld Windows Service 足以证明 Server 在线；认证单独处理。
            $admin = Join-Path (Split-Path -Parent $MySqlExe) 'mysqladmin.exe'
            if (Test-Path $admin) {
                $ping = & $admin '--protocol=TCP' '-h' '127.0.0.1' '-P' '3306' '-u' 'root' 'ping' '--connect-timeout=1' 2>&1
                if ($LASTEXITCODE -eq 0) { Write-SetupLog 'mysqladmin TCP ping succeeded.'; return }
                $detail = $ping -join ' '
                if ($detail -match '(?i)(access denied|error\s+1045)') { Write-SetupLog 'mysqladmin reached MySQL but root authentication was denied; continuing to root-auth handling.'; return }
                Write-SetupLog ("mysqladmin ping exit code $LASTEXITCODE after TCP readiness: " + $detail)
                return
            }
            Write-SetupLog 'mysqladmin.exe not found; accepted service Running + TCP readiness.'
            return
        }
        Start-Sleep -Seconds 1
    }
    throw 'MySQL 服务已启动，但 60 秒内未能确认 127.0.0.1:3306 上的 MySQL 已就绪。'
}

function Invoke-DatabaseInit {
    param([string]$MySqlExe)
    $initScript = Join-Path $scriptDir 'init_database.ps1'
    if (-not (Test-Path $initScript)) { throw "未找到初始化脚本：$initScript" }
    & $initScript -MySqlExe $MySqlExe
    if ($LASTEXITCODE -ne 0) { throw "init_database.ps1 失败（exit code $LASTEXITCODE）。" }
}

function Get-DotEnvValues {
    param([string]$Path)
    if (-not (Test-Path $Path)) { throw "未找到 backend/.env：$Path" }
    $values = @{}
    foreach ($line in Get-Content -LiteralPath $Path) {
        if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)=(.*)$') { $values[$matches[1]] = $matches[2] }
    }
    foreach ($key in @('DB_HOST','DB_PORT','DB_NAME','DB_USER','DB_PASSWORD','DB_CHARSET')) {
        if (-not $values.ContainsKey($key) -or [string]::IsNullOrWhiteSpace($values[$key])) { throw "backend/.env 缺少 $key。" }
    }
    return $values
}

function Test-ProjectDatabase {
    param([string]$MySqlExe)
    $envValues = Get-DotEnvValues (Join-Path $repoRoot 'backend\.env')
    $requiredTables = @('news_articles','favorites','feedback','model_evaluations')
    $oldPassword = $env:MYSQL_PWD
    $hadPassword = Test-Path Env:\MYSQL_PWD
    $env:MYSQL_PWD = $envValues['DB_PASSWORD']
    try {
        $escapedDbName = $envValues['DB_NAME'].Replace("'", "''")
        $query = "SELECT table_name FROM information_schema.tables WHERE table_schema='$escapedDbName' AND table_name IN ('news_articles','favorites','feedback','model_evaluations') ORDER BY table_name;"
        $result = & $MySqlExe '-h' $envValues['DB_HOST'] '-P' $envValues['DB_PORT'] '-u' $envValues['DB_USER'] '--default-character-set=utf8mb4' '-N' '-B' '-e' $query 2>&1
        if ($LASTEXITCODE -ne 0) { throw 'news_app 无法连接项目数据库（密码未输出）。' }
        $actual = @($result | ForEach-Object { $_.ToString().Trim() } | Where-Object { $_ })
        foreach ($table in $requiredTables) {
            if ($actual -notcontains $table) { throw "最终验证失败：缺少表 $table。" }
        }
        Write-Host '      PASS - news_summary 存在，news_app 可以连接。' -ForegroundColor Green
        foreach ($table in $requiredTables) {
            Write-Host ("      PASS - " + $table) -ForegroundColor Green
        }
    } finally {
        if ($hadPassword) { $env:MYSQL_PWD = $oldPassword } else { Remove-Item Env:\MYSQL_PWD -ErrorAction SilentlyContinue }
    }
}

try {
    Write-SetupLog '--- setup_database.ps1 started (passwords are never logged) ---'
    Write-Host '=====================================================' -ForegroundColor Cyan
    Write-Host ' NewsSummarySystem - 数据库首次部署' -ForegroundColor Cyan
    Write-Host '=====================================================' -ForegroundColor Cyan

    Invoke-ElevatedSelf | Out-Null

    $services = @(Get-MySqlServices)
    $candidate = Select-MySqlService $services
    $projectInstall = Get-ProjectBootstrapInstall $candidate
    if (-not $candidate) {
        if ($services.Count -gt 0) { throw '检测到 MySQL Windows Service，但无法从其服务路径安全识别可用的 MySQL Server 实例。脚本不会覆盖、重装或猜测配置。' }
        $binaries = @(Find-MySqlServerBinaries)
        $recoverableInstall = Get-OfficialUnconfiguredInstall -ServerBinaries $binaries -Services $services
        if ($recoverableInstall) {
            Write-StepResult '1/7' 'PASS' ("发现尚未配置的官方 MySQL Server {0}" -f $recoverableInstall.Version)
            Write-StepResult '2/7' 'SKIP' '官方安装已存在，进入首次实例配置'
            Initialize-OfficialMySqlInstall $recoverableInstall
            $projectInstall = $recoverableInstall
        } elseif ($binaries.Count -gt 0) {
            throw "发现 mysqld.exe 但没有可安全确认的官方未配置安装：$($binaries -join '; ')。脚本不会以未知配置创建或启动服务。"
        } else {
            Write-StepResult '1/7' 'SKIP' '未发现可用 MySQL Server'
            Write-StepResult '2/7' 'PASS' '开始通过 winget 安装 MySQL Server'
            Install-MySqlServer
            $binaries = @(Find-MySqlServerBinaries)
            $recoverableInstall = Get-OfficialUnconfiguredInstall -ServerBinaries $binaries -Services @()
            if ($recoverableInstall) { Initialize-OfficialMySqlInstall $recoverableInstall; $projectInstall = $recoverableInstall }
        }
        # 初始化/注册后必须重新枚举，而不能假定服务名称或路径。
        $services = @(Get-MySqlServices)
        $candidate = Select-MySqlService $services
        if (-not $candidate) { throw '首次初始化结束后仍未发现配置为 3306、版本至少 8.0.16 的 MySQL Windows Service。' }
        $projectInstall = Get-ProjectBootstrapInstall $candidate
    } else {
        $label = if ($projectInstall) { '已发现项目 MySQL Server' } else { '已发现 MySQL Server' }
        Write-StepResult '1/7' 'PASS' ("{0} {1}" -f $label, $candidate.Version)
        Write-StepResult '2/7' 'PASS' ("Windows Service 已存在：{0}" -f $candidate.Service.Name)
    }

    $mysqlExe = Find-MySqlClient $candidate.Service.ServerPath
    if (-not $mysqlExe) { throw '已找到 MySQL Server，但未找到同实例可用的 mysql.exe 客户端。' }
    Write-StepResult '3/7' 'PASS' ("Windows Service: {0}" -f $candidate.Service.Name)
    Start-MySqlService $candidate
    Write-StepResult '4/7' 'PASS' 'Running'
    if ($candidate.Version -lt $minimumVersion) { throw "MySQL Server 版本 $($candidate.Version) 不满足最低要求 $minimumVersion。不会自动升级现有数据库。" }
    Write-StepResult '5/7' 'PASS' ("{0} >= {1}" -f $candidate.Version, $minimumVersion)
    Wait-MySqlReady -ServiceName $candidate.Service.Name -MySqlExe $mysqlExe
    Write-Host '      MySQL 已响应 127.0.0.1:3306。' -ForegroundColor Green
    Ensure-RootAuthentication -MySqlExe $mysqlExe -ProjectInstall $projectInstall
    Write-StepResult '5/7' 'PASS' 'Root authentication 已处理'
    Invoke-DatabaseInit $mysqlExe
    Write-StepResult '6/7' 'PASS' 'init_database.ps1 成功'
    Test-ProjectDatabase $mysqlExe
    Write-StepResult '7/7' 'PASS' 'news_summary、news_app 与 4 张核心表均已验证'
    Write-Host '=====================================================' -ForegroundColor Cyan
    Write-Host ' 数据库首次部署完成' -ForegroundColor Green
    Write-Host '=====================================================' -ForegroundColor Cyan
    exit 0
} catch {
    Write-Host ("[FAIL] " + $_.Exception.Message) -ForegroundColor Red
    exit 1
}
