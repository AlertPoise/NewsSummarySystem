# Non-destructive tests: no venv, pip, GPU, or system configuration is changed.
$ErrorActionPreference='Stop'
$script=Join-Path (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)) 'setup_runtime_env.ps1'
. $script -SkipMain
function Assert-Equal($actual,$expected,[string]$name){if($actual -ne $expected){throw "${name}: expected '$expected', got '$actual'."};Write-Host "PASS - $name" -ForegroundColor Green}

$before=$ErrorActionPreference
$capture=Invoke-NativeCommandCapture $env:ComSpec @('/c','echo expected stderr 1>&2 & exit /b 7')
Assert-Equal $capture.ExitCode 7 'native stderr non-zero exit is captured'
Assert-Equal $ErrorActionPreference $before 'ErrorActionPreference restored after native capture'

$seed=(Get-Command python -ErrorAction Stop).Source
$testLog=Join-Path ([IO.Path]::GetTempPath()) ('NewsSummarySystem-runtime-stream-' + [guid]::NewGuid().ToString('N') + '.log')
try{
    $logFile=$testLog
    # Run in a separate process so the parent can prove that the log changes while
    # the native action is still running, rather than only after it exits.
    $streamCode="import time; print('tick-0'); time.sleep(2); print('tick-1'); time.sleep(2); print('tick-2')"
    $job=Start-Job -ScriptBlock { param($setup,$log,$python,$code); . $setup -SkipMain; $logFile=$log; Run 'streaming test action' $python @('-u','-c',$code) } -ArgumentList $script,$testLog,$seed,$streamCode
    Start-Sleep -Milliseconds 1200
    Assert-Equal $job.State 'Running' 'long native action remains running during stream check'
    Assert-Equal ((Get-Content -LiteralPath $testLog -Raw) -match 'tick-0') $true 'first stdout line reaches log before action exits'
    Receive-Job -Job $job -Wait -AutoRemoveJob | Out-Null

    Run 'stderr success test' $seed @('-u','-c',"import sys; print('stderr-success', file=sys.stderr)")
    Assert-Equal ((Get-Content -LiteralPath $testLog -Raw) -match 'stderr-success') $true 'stderr with exit 0 is streamed and logged'
    try{Run 'stderr failure test' $seed @('-u','-c',"import sys; print('stderr-failure', file=sys.stderr); raise SystemExit(1)");throw 'Run accepted stderr plus exit 1'}catch{if($_.Exception.Message -notmatch 'exit code 1'){throw};Write-Host 'PASS - stderr plus exit 1 remains fatal' -ForegroundColor Green}
    Assert-Equal ((Get-Content -LiteralPath $testLog -Raw) -match 'stderr-failure') $true 'stderr with exit 1 is streamed and logged'
    Assert-Equal $ErrorActionPreference $before 'ErrorActionPreference restored after streaming actions'
}finally{
    if($job){Remove-Job -Job $job -Force -ErrorAction SilentlyContinue}
    if(Test-Path -LiteralPath $testLog){Remove-Item -LiteralPath $testLog -Force}
}

$testVenv=Join-Path ([IO.Path]::GetTempPath()) ('NewsSummarySystem-runtime-test-' + [guid]::NewGuid().ToString('N'))
try{
    $venvCreate=Invoke-NativeCommandCapture $seed @('-m','venv',$testVenv)
    Assert-Equal $venvCreate.ExitCode 0 'fresh temporary venv is created'
    Assert-Equal (Get-Torch (Join-Path $testVenv 'Scripts\python.exe')) $null 'fresh venv without torch returns null'
}finally{
    if(Test-Path -LiteralPath $testVenv){Remove-Item -LiteralPath $testVenv -Recurse -Force}
}

function Log([string]$m){Write-Host $m}
function Get-Command([string]$Name,[Parameter(ValueFromRemainingArguments=$true)]$Rest){
    if($Name -in @('py','python')){return [PSCustomObject]@{Source='fake-python'}}
    return $null
}
function Invoke-NativeCommandCapture([string]$file,[string[]]$arguments){
    if($arguments -contains '-3.12'){return [PSCustomObject]@{ExitCode=1;Output='Python 3.12 is not installed'}}
    return [PSCustomObject]@{ExitCode=0;Output="C:\Python311\python.exe`n3`n11`n9`n9223372036854775807"}
}
$candidates=@(Get-PythonCandidates)
Assert-Equal (@($candidates|Where-Object Launcher -eq 'py -3.12').Count) 0 'unavailable py -3.12 is skipped without aborting selection'
Assert-Equal (@($candidates|Where-Object {$_.Major -eq 3 -and $_.Minor -eq 11}).Count -gt 0) $true 'other Python candidates remain usable'

$script:fakeResult=[PSCustomObject]@{ExitCode=1;Output="Traceback (most recent call last):`nModuleNotFoundError: No module named 'torch'"}
function Invoke-NativeCommandCapture([string]$file,[string[]]$arguments){$script:fakeResult}
Assert-Equal (Get-Torch 'fake-python') $null 'missing torch is a normal probe result'
$script:fakeResult=[PSCustomObject]@{ExitCode=0;Output="2.14.0+cu126`n12.6"}
$torch=Get-Torch 'fake-python'
Assert-Equal $torch.Version '2.14.0+cu126' 'compatible torch version is parsed'
Assert-Equal $torch.Cuda '12.6' 'compatible torch CUDA runtime is parsed'
