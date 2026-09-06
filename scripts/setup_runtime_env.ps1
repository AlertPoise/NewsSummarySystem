#Requires -Version 5.1
<# Creates the isolated, reproducible NewsSummarySystem runtime at <repo>\.venv. #>
[CmdletBinding()] param([switch]$SkipMain)
$ErrorActionPreference='Stop'; $ProgressPreference='SilentlyContinue'
$repoRoot=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$runtimeVenv=Join-Path $repoRoot '.venv'; $runtimePython=Join-Path $runtimeVenv 'Scripts\python.exe'
$requirementsFile=Join-Path $repoRoot 'backend\requirements.txt'; $runtimeDir=Join-Path $repoRoot 'runtime'
$logFile=Join-Path $runtimeDir 'setup_runtime_env.log'; $tunaIndex='https://pypi.tuna.tsinghua.edu.cn/simple'; $njuBase='https://mirrors.nju.edu.cn/pytorch/whl'
$pipNetworkArgs=@('--timeout','30','--retries','2')
# This is the project verification matrix. Add cu128/cu130 only after testing this exact version.
$TorchVersion='2.14.0'
$SupportedTorchChannels=@(
 [PSCustomObject]@{Channel='cu126';RuntimeMode='CUDA';MinimumDriverCuda=[version]'12.6';Reason='项目已验证的最高稳定 CUDA channel（驱动能力 >= 12.6）'},
 [PSCustomObject]@{Channel='cpu';RuntimeMode='CPU';MinimumDriverCuda=$null;Reason='CPU runtime（无可用 NVIDIA GPU 或驱动能力不足）'} )
if(-not $SkipMain){New-Item -ItemType Directory -Force -Path $runtimeDir|Out-Null;Set-Content -LiteralPath $logFile -Value ("Setup started: {0:u}" -f (Get-Date)) -Encoding UTF8}
function Log([string]$m){Write-Host $m;Add-Content -LiteralPath $logFile -Value $m -Encoding UTF8}
function Fail([string]$m){Log "[FAIL] $m";throw $m}
function Invoke-NativeCommandCapture([string]$file,[string[]]$arguments){
 # Windows PowerShell 5.1 can turn native stderr into a terminating ErrorRecord
 # under ErrorActionPreference=Stop.  Native programs are classified by callers.
 if(-not $file -or -not (Test-Path -LiteralPath $file)){throw "Native executable not found: $file"}
 $previousPreference=$ErrorActionPreference
 try{$ErrorActionPreference='Continue';$output=& $file @arguments 2>&1;$exitCode=$LASTEXITCODE}
 finally{$ErrorActionPreference=$previousPreference}
 return [PSCustomObject]@{ExitCode=$exitCode;Output=(($output|ForEach-Object{$_.ToString()}) -join "`n")}
}
function Run([string]$label,[string]$file,[string[]]$arguments,[string]$hint=''){
 Log "      $label";$result=Invoke-NativeCommandCapture $file $arguments
 if($result.Output){$result.Output -split "`r?`n"|ForEach-Object{Write-Host $_;Add-Content -LiteralPath $logFile -Value $_ -Encoding UTF8}}
 if($result.ExitCode -ne 0){throw "$label failed (exit code $($result.ExitCode)). $hint"}
}
function Test-Mirror([string]$name,[string]$url){try{$r=Invoke-WebRequest -Uri "$url/" -UseBasicParsing -TimeoutSec 30;if($r.StatusCode -lt 200 -or $r.StatusCode -ge 400){throw "HTTP $($r.StatusCode)"};Log "      PASS - $name is reachable ($url)"}catch{Fail "$name 镜像不可访问：$url。不会回退到官方源。详情：$($_.Exception.Message)"}}
function Get-PythonCandidates {
 $code='import sys;print(sys.executable);print(sys.version_info[0]);print(sys.version_info[1]);print(sys.version_info[2]);print(sys.maxsize)'
 $specs=@(); $py=Get-Command py -EA SilentlyContinue
 if($py){$specs+=@{F=$py.Source;A=@('-3.11');N='py -3.11'};$specs+=@{F=$py.Source;A=@('-3.12');N='py -3.12'};$specs+=@{F=$py.Source;A=@();N='py default'}}
 $p=Get-Command python -EA SilentlyContinue;if($p){$specs+=@{F=$p.Source;A=@();N='python'}};$found=@()
 foreach($s in $specs){try{$result=Invoke-NativeCommandCapture $s.F (@($s.A)+@('-c',$code));$o=@($result.Output -split "`r?`n"|Where-Object{$_ -ne ''});if($result.ExitCode -ne 0 -or $o.Count -lt 5){Log "      Candidate $($s.N) unavailable / skipped (exit code $($result.ExitCode)).";continue};$maj=[int]$o[1];$min=[int]$o[2];$bits=if([int64]$o[4] -gt 2147483647){64}else{32};$path=[IO.Path]::GetFullPath([string]$o[0]);$lower=$path.ToLowerInvariant();$cp=if($env:CONDA_PREFIX){$env:CONDA_PREFIX.ToLowerInvariant()}else{''};$found+=[PSCustomObject]@{Launcher=$s.N;Executable=$path;Major=$maj;Minor=$min;Version="$($maj).$($min).$([int]$o[3])";Bits=$bits;IsConda=($lower -match '\\(anaconda|miniconda|miniforge|mambaforge|conda)\\' -or ($cp -and $lower.StartsWith($cp)));IsVenv=($lower -match '\\scripts\\python\.exe$')}}catch{Log "      Candidate $($s.N) unavailable / skipped."}}
 return $found
}
function Select-TorchPlan([bool]$gpu,[version]$cuda){if(-not $gpu -or -not $cuda){return $SupportedTorchChannels|Where-Object Channel -eq cpu|Select-Object -First 1};$p=$SupportedTorchChannels|Where-Object{$_.RuntimeMode -eq 'CUDA' -and $cuda -ge $_.MinimumDriverCuda}|Sort-Object MinimumDriverCuda -Descending|Select-Object -First 1;if($p){return $p};return $SupportedTorchChannels|Where-Object Channel -eq cpu|Select-Object -First 1}
function Test-TorchWheel([string]$index,[string]$channel,[string]$abi){try{$response=Invoke-WebRequest -Uri "$index/torch/" -UseBasicParsing -TimeoutSec 30;$needle="torch-$TorchVersion%2B${channel}-${abi}-${abi}-win_amd64.whl";$wheel=$response.Links|Where-Object{$_.href -like "*$needle*"}|Select-Object -First 1;if(-not $wheel){Fail "PyTorch channel 存在，但找不到 torch $TorchVersion / $channel / $abi / Windows x64 wheel。可能是该 Python、torch 版本和 CUDA channel 组合不受支持。"};Log "      PASS - found torch $TorchVersion $channel wheel for ${abi}-win_amd64"}catch{if($_.Exception.Message -like '*找不到 torch*'){throw};Fail "无法预检南京大学 PyTorch wheel。不会回退官方源。详情：$($_.Exception.Message)"}}
function Get-Torch([string]$p){$result=Invoke-NativeCommandCapture $p @('-c','import torch;print(torch.__version__);print(torch.version.cuda or "cpu")');$o=@($result.Output -split "`r?`n"|Where-Object{$_ -ne ''});if($result.ExitCode -ne 0 -or $o.Count -lt 2){return $null};return [PSCustomObject]@{Version=([string]$o[0]).Trim();Cuda=([string]$o[1]).Trim()}}
$tempRequirements=$null
if(-not $SkipMain){try{
 Log '=====================================================';Log ' NewsSummarySystem - 正式运行环境配置';Log '=====================================================';Log "Diagnostic only: VIRTUAL_ENV=$($env:VIRTUAL_ENV)";Log "Diagnostic only: CONDA_PREFIX=$($env:CONDA_PREFIX)"
 Log '[1/7] Python'
 $candidates=@(Get-PythonCandidates)
 $candidates|ForEach-Object{Log "      Candidate: $($_.Executable) | Python $($_.Version) | $($_.Bits)-bit | Conda=$($_.IsConda) | venv=$($_.IsVenv)"}
 $supported=$candidates|Where-Object{$_.Bits -eq 64 -and $_.Major -eq 3 -and $_.Minor -in @(11,12)}
 $selected=$supported|Where-Object{-not $_.IsConda -and -not $_.IsVenv}|Sort-Object Minor|Select-Object -First 1
 if(-not $selected){$selected=$supported|Where-Object{$_.IsConda -and -not $_.IsVenv}|Sort-Object Minor|Select-Object -First 1}
 if(-not $selected){$u=$candidates|Where-Object{-not $_.IsVenv}|Select-Object -First 1;if($u -and $u.Bits -ne 64){Fail '检测到的 Python 不是 64 位；正式运行环境只支持 64 位 CPython 3.11 / 3.12。'};if($u){Fail ('检测到 Python ' + $u.Version + '，但项目仅支持并验证 Python 3.11 / 3.12。请安装受支持版本后重试。')};Fail '未检测到可用 Python。请安装 64 位 CPython 3.11（推荐）或 3.12。'}
 if($selected.IsConda){Log '      WARN - only a supported Conda Python was found; it is used only to create root .venv.'}
 Log "      PASS - Python $($selected.Version), $($selected.Bits)-bit"
 Log "      Seed interpreter: $($selected.Executable) ($($selected.Launcher))"
 Log '[2/7] 创建正式虚拟环境'
 if(-not (Test-Path -LiteralPath $runtimePython)){if(Test-Path -LiteralPath $runtimeVenv){Fail "已有 .venv 但缺少或损坏 $runtimePython；脚本不会自动删除它。"};Run 'Creating root .venv' $selected.Executable @('-m','venv',$runtimeVenv)}
 $probe=Invoke-NativeCommandCapture $runtimePython @('-c','import platform,sys;print(sys.executable);print(sys.version_info[0]);print(sys.version_info[1]);print(platform.architecture()[0])')
 $pt=$probe.Output
 if($probe.ExitCode -ne 0){Fail "根目录 .venv 无法执行：$runtimePython"}
 if($pt -notmatch '64bit'){Fail "根目录 .venv 不是 64 位：$runtimePython"}
 if($pt -notmatch "`n3`n(11|12)`n"){Fail "根目录 .venv 的 Python 不在支持范围 3.11 / 3.12：$runtimePython"}
 $abi="cp3$($Matches[1])"
 Log "      PASS - $runtimeVenv ($abi, 64-bit)"
 Log '[3/7] GPU 检测';$gpu=$false;$gpuName='N/A';$driver='N/A';$driverCuda=$null;$smi=Get-Command nvidia-smi -EA SilentlyContinue;if($smi){$q=Invoke-NativeCommandCapture $smi.Source @('--query-gpu=name,driver_version','--format=csv,noheader');$summary=Invoke-NativeCommandCapture $smi.Source @();if($q.ExitCode -eq 0 -and $summary.ExitCode -eq 0 -and $q.Output){$parts=([string](($q.Output -split "`r?`n"|Select-Object -First 1)))-split ',\s*',2;$gpuName=$parts[0].Trim();if($parts.Count -gt 1){$driver=$parts[1].Trim()};if($summary.Output -match 'CUDA Version:\s*([0-9]+\.[0-9]+)'){$driverCuda=[version]$Matches[1]};$gpu=$true}else{Log "      nvidia-smi unavailable / skipped (query exit code $($q.ExitCode), summary exit code $($summary.ExitCode))."}};Log "      GPU detected: $gpu";Log "      GPU name: $gpuName";Log "      Driver version: $driver";Log "      Driver CUDA capability: $driverCuda"
 Log '[4/7] PyTorch 安装策略';$plan=Select-TorchPlan $gpu $driverCuda;$mode=$plan.RuntimeMode;$channel=$plan.Channel;$why=if($gpu -and $mode -eq 'CPU'){"检测到 NVIDIA GPU，但驱动能力不足；$($plan.Reason)"}else{$plan.Reason};$index="$njuBase/$channel";Log "      Selected runtime mode: $mode";Log "      Selected torch version: $TorchVersion";Log "      Selected torch channel: $channel";Log "      Why selected: $why";Log "      Selected PyTorch mirror: $index";Log "      Tsinghua PyPI mirror: $tunaIndex";Test-Mirror '清华 PyPI' $tunaIndex;Test-Mirror '南京大学 PyTorch channel' $index;Test-TorchWheel $index $channel $abi;$expected=if($mode -eq 'CUDA'){($channel -replace '^cu','').Insert(2,'.')}else{'cpu'};$old=Get-Torch $runtimePython;$reuse=$old -and $old.Version -eq "$TorchVersion+$channel" -and $old.Cuda -eq $expected;if($reuse){Log "      PASS - reusing compatible torch $($old.Version) (torch.version.cuda=$($old.Cuda))"}else{if($old){Log "      Existing torch incompatible: version=$($old.Version), cuda=$($old.Cuda); target=$TorchVersion+$channel / $expected"};Run 'Installing pinned PyTorch wheel from Nanjing University mirror' $runtimePython (@('-m','pip','install','--upgrade','--force-reinstall','--no-deps','-i',$index)+$pipNetworkArgs+@("torch==$TorchVersion+$channel")) '可能是该 Python / torch / CUDA channel 组合不存在 Windows x64 wheel。'}
 Log '[5/7] 安装项目依赖';if(-not (Test-Path -LiteralPath $requirementsFile)){Fail "未找到运行依赖文件：$requirementsFile"};$lines=Get-Content -LiteralPath $requirementsFile;$aux=$lines|Where-Object{$_ -match '^\s*(torchvision|torchaudio|torchtext)(?:\s|$|[<>=!~;\[])'};if($aux){Fail "requirements.txt 包含 torchvision/torchaudio/torchtext；必须先固定为与 torch $TorchVersion / $channel 匹配的版本，脚本不会让 resolver 自动替换 torch。"};$tempRequirements=[IO.Path]::GetTempFileName();Set-Content -LiteralPath $tempRequirements -Value ($lines|Where-Object{$_ -notmatch '^\s*torch(?:\s|$|[<>=!~;\[])'}) -Encoding UTF8;Run 'Upgrading pip/setuptools/wheel via Tsinghua mirror' $runtimePython (@('-m','pip','install','--upgrade','-i',$tunaIndex)+$pipNetworkArgs+@('pip','setuptools','wheel'));Run 'Installing PyTorch runtime dependencies via Tsinghua mirror' $runtimePython (@('-m','pip','install','-i',$tunaIndex)+$pipNetworkArgs+@('filelock','typing-extensions','networkx','jinja2','fsspec','sympy'));Run 'Installing project dependencies (torch excluded) via Tsinghua mirror' $runtimePython (@('-m','pip','install','-i',$tunaIndex)+$pipNetworkArgs+@('-r',$tempRequirements)) '可能存在 requirements 依赖冲突；完整 pip 输出已写入日志。';Run 'Checking installed package consistency' $runtimePython @('-m','pip','check') 'requirements 依赖冲突。';Log '      PASS - Mirror: 清华大学'
 Log '[6/7] PyTorch 验证';$verify=@'
import os, sys, torch
print('Python executable:', sys.executable); print('Python version:', sys.version); print('torch.__version__:', torch.__version__); print('torch.version.cuda:', torch.version.cuda); print('torch.cuda.is_available():', torch.cuda.is_available())
if os.environ['EXPECTED_MODE'] == 'CUDA':
    assert torch.cuda.is_available(), 'CUDA PyTorch installed but CUDA is unavailable'
    assert torch.cuda.device_count() > 0, 'No CUDA device is available'
    print('GPU:', torch.cuda.get_device_name(0)); x=torch.tensor([1.0], device='cuda'); y=x*2; torch.cuda.synchronize(); print('CUDA tensor result:', y.item())
else:
    x=torch.tensor([1.0]); print('Runtime mode: CPU'); print('CPU tensor result:', (x*2).item())
'@
 $env:EXPECTED_MODE=$mode;Run 'Running actual PyTorch tensor operation' $runtimePython @('-c',$verify) 'CUDA runtime was selected but could not run; setup intentionally does not downgrade to CPU.';Remove-Item Env:EXPECTED_MODE -EA SilentlyContinue;Log '      PASS'
 Log '[7/7] 核心依赖验证';$imports=@'
import os, pathlib
import fastapi, uvicorn, sqlalchemy, pymysql, pydantic_settings, dotenv, torch, transformers, yaml
root=pathlib.Path(os.environ['RUNTIME_SITE_ROOT']).resolve()
for m in (torch,transformers):
    p=pathlib.Path(m.__file__).resolve(); assert root in p.parents, f'{m.__name__} was imported outside .venv: {p}'; print(f'{m.__name__}: {p}')
print('All core imports passed')
'@
 $env:RUNTIME_SITE_ROOT=(Join-Path $runtimeVenv 'Lib\site-packages');Run 'Importing all core runtime dependencies' $runtimePython @('-c',$imports);Remove-Item Env:RUNTIME_SITE_ROOT -EA SilentlyContinue;Log '      PASS - Final environment validation result: SUCCESS'
 Log '=====================================================';Log ' 正式运行环境配置完成';Log '=====================================================';Log "Python executable: $runtimePython";Log "Python version: $($selected.Version)";Log 'Architecture: 64-bit';Log "GPU detected: $gpu";Log "GPU name: $gpuName";Log "Driver version: $driver";Log "Driver CUDA capability: $driverCuda";Log "Selected runtime mode: $mode";Log "Selected torch version: $TorchVersion";Log "Selected torch channel: $channel";Log "Selected PyTorch mirror: $index";Log "Tsinghua PyPI mirror: $tunaIndex";exit 0
}catch{Log "Setup failed: $($_.Exception.Message)";exit 1}finally{if($tempRequirements -and (Test-Path -LiteralPath $tempRequirements)){Remove-Item -LiteralPath $tempRequirements -Force};Remove-Item Env:EXPECTED_MODE -EA SilentlyContinue;Remove-Item Env:RUNTIME_SITE_ROOT -EA SilentlyContinue}}
