# B 角色离线训练 Python 环境初始化脚本。
$ErrorActionPreference = "Stop"

$PipIndexUrl = "https://pypi.tuna.tsinghua.edu.cn/simple"
$PyTorchWheelBaseUrl = "https://download.pytorch.org/whl"
$env:PIP_INDEX_URL = $PipIndexUrl
$ScriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepositoryRoot = Split-Path -Parent $ScriptDirectory
$VenvDirectory = Join-Path $RepositoryRoot ".venv"
$VenvPython = Join-Path $VenvDirectory "Scripts\\python.exe"
$RequirementsPath = Join-Path $ScriptDirectory "requirements.txt"

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "命令执行失败（退出码 $LASTEXITCODE）：$FilePath $($Arguments -join ' ')"
    }
}

function Get-Python311Command {
    $PythonLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($null -ne $PythonLauncher) {
        $PyVersionArguments = @("-3.11", "--version")
        $VersionOutput = & py @PyVersionArguments
        $VersionExitCode = $LASTEXITCODE
        $VersionOutput = $VersionOutput | Select-Object -First 1
        $VersionText = if ($null -eq $VersionOutput) { "" } else { $VersionOutput.Trim() }
        if ($VersionExitCode -eq 0 -and $VersionText -match '^Python 3\.11\.\d+$') {
            return @{ FilePath = "py"; Arguments = @("-3.11") }
        }
    }

    $PythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($null -eq $PythonCommand) {
        throw "未找到 Python 3.11。请安装 Python 3.11 并确保 py -3.11 或 python 可用。"
    }

    $PythonVersionArguments = @("--version")
    $VersionOutput = & python @PythonVersionArguments
    $VersionExitCode = $LASTEXITCODE
    $VersionOutput = $VersionOutput | Select-Object -First 1
    $VersionText = if ($null -eq $VersionOutput) { "" } else { $VersionOutput.Trim() }
    if ($VersionExitCode -ne 0 -or $VersionText -notmatch '^Python 3\.11\.\d+$') {
        throw "当前 python 不是 Python 3.11（检测到：$VersionText）。请安装或指定 Python 3.11。"
    }

    return @{ FilePath = "python"; Arguments = @() }
}

try {
    Write-Host "正在初始化 B 离线训练 Python 环境。"
    Write-Host "当前 Python 包镜像："
    Write-Host $PipIndexUrl

    if (-not (Test-Path -LiteralPath $RequirementsPath -PathType Leaf)) {
        throw "未找到 B 依赖文件：$RequirementsPath"
    }

    $PythonCommand = Get-Python311Command
    $BasePython = $PythonCommand.FilePath
    $BasePythonArguments = [string[]]$PythonCommand.Arguments
    $BaseVersionArguments = $BasePythonArguments + @("--version")
    $PythonVersionOutput = & $BasePython @BaseVersionArguments
    $PythonVersionExitCode = $LASTEXITCODE
    $PythonVersion = ($PythonVersionOutput | Select-Object -First 1).Trim()
    if ($PythonVersionExitCode -ne 0) {
        throw "无法读取 Python 版本。"
    }
    Write-Host "已确认 Python：$PythonVersion"

    if (-not (Test-Path -LiteralPath $VenvDirectory)) {
        Write-Host "正在创建虚拟环境：$VenvDirectory"
        Invoke-Checked -FilePath $BasePython -Arguments ($BasePythonArguments + @("-m", "venv", $VenvDirectory))
    }

    if (-not (Test-Path -LiteralPath $VenvPython -PathType Leaf)) {
        throw "虚拟环境不完整：未找到 $VenvPython。为避免删除现有目录，脚本已停止；请由用户决定是否重建 .venv。"
    }

    Invoke-Checked -FilePath $VenvPython -Arguments @("--version")
    Write-Host "正在通过清华镜像升级 pip、setuptools、wheel。"
    Invoke-Checked -FilePath $VenvPython -Arguments @("-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel", "--index-url", $PipIndexUrl)

    Write-Host "正在通过清华镜像安装 B 离线训练依赖。"
    Invoke-Checked -FilePath $VenvPython -Arguments @("-m", "pip", "install", "--index-url", $PipIndexUrl, "-r", $RequirementsPath)

    $NvidiaSmi = Get-Command nvidia-smi -ErrorAction SilentlyContinue
    $TorchIndexUrl = "https://download.pytorch.org/whl/cpu"
    $TorchTarget = "cpu"
    $GpuDetected = $false
    if ($null -ne $NvidiaSmi) {
        $GpuRows = & nvidia-smi --query-gpu=name,driver_version --format=csv,noheader
        $GpuQueryExitCode = $LASTEXITCODE
        $NvidiaSummary = & nvidia-smi
        $NvidiaSummaryExitCode = $LASTEXITCODE
        if ($GpuQueryExitCode -ne 0 -or $NvidiaSummaryExitCode -ne 0) {
            throw "nvidia-smi 执行失败，无法可靠确定 NVIDIA 驱动与 CUDA Runtime 能力。"
        }
        $CudaMatch = [regex]::Match(($NvidiaSummary -join "`n"), "CUDA Version:\s*(\d+\.\d+)")
        if (-not $CudaMatch.Success) {
            throw "无法从 nvidia-smi 可靠读取驱动支持的 CUDA Runtime 能力。"
        }
        $DriverCudaCapability = [version]$CudaMatch.Groups[1].Value
        Write-Host "检测到 NVIDIA GPU：$($GpuRows -join '; ')"
        Write-Host "驱动支持 CUDA Runtime：$DriverCudaCapability"
        # 来源：PyTorch 官方 Stable Windows pip wheel 矩阵。
        # 仅保留经官方矩阵确认的稳定 CUDA wheel；按驱动能力降序选择最高兼容项。
        $StableCudaWheels = @(
            @{ Tag = "cu132"; Runtime = [version]"13.2" },
            @{ Tag = "cu130"; Runtime = [version]"13.0" },
            @{ Tag = "cu126"; Runtime = [version]"12.6" }
        )
        $CompatibleWheel = $StableCudaWheels | Where-Object { $DriverCudaCapability -ge $_.Runtime } | Select-Object -First 1
        if ($null -eq $CompatibleWheel) {
            throw "检测到 NVIDIA GPU，但当前驱动不足以支持已验证的正式 PyTorch CUDA wheel；请升级 NVIDIA 驱动。"
        }
        $TorchTarget = $CompatibleWheel.Tag
        $TorchIndexUrl = "$PyTorchWheelBaseUrl/$TorchTarget"
        $GpuDetected = $true
    } else {
        Write-Warning "未检测到 NVIDIA GPU 或 nvidia-smi；将安装官方 CPU PyTorch（CPU fallback）。"
    }

    $TorchProbe = & $VenvPython -c "import torch; print(f'{torch.__version__}|{torch.version.cuda}|{torch.cuda.is_available()}')" 2>$null
    $TorchProbeExitCode = $LASTEXITCODE
    $ExpectedCudaRuntime = if ($GpuDetected) { $CompatibleWheel.Runtime.ToString() } else { "None" }
    $TorchIsReady = $false
    if ($TorchProbeExitCode -eq 0) {
        $TorchParts = $TorchProbe.Trim().Split("|")
        $TorchIsReady = ($TorchParts[1] -eq $ExpectedCudaRuntime)
        if ($GpuDetected) { $TorchIsReady = $TorchIsReady -and ($TorchParts[2] -eq "True") }
        Write-Host "当前 PyTorch：$TorchProbe；目标 wheel：$TorchTarget"
    }
    if (-not $TorchIsReady) {
        Write-Host "PyTorch wheel 来源：官方 download.pytorch.org；正在安装：$TorchTarget"
        Write-Host "仅从官方源获取 torch wheel；不使用 --force-reinstall，且不让其重复解析/下载普通依赖。"
        Invoke-Checked -FilePath $VenvPython -Arguments @("-m", "pip", "install", "--upgrade", "--no-deps", "torch", "--index-url", $TorchIndexUrl)
    } else {
        Write-Host "现有 PyTorch 已满足当前目标，不重复安装。"
    }

    Write-Host "正在验证核心依赖与 PyTorch CUDA 状态。"
    $VerificationCode = @(
        'import sys',
        'print(f"Python version: {sys.version}")',
        'for package_name in ("torch", "transformers", "datasets", "accelerate", "evaluate", "rouge_score", "sentencepiece", "safetensors", "yaml", "tqdm", "numpy"):',
        '    print(f"正在导入: {package_name}")',
        '    __import__(package_name)',
        'import accelerate',
        'import datasets',
        'import torch',
        'import transformers',
        'print(f"PyTorch version: {torch.__version__}")',
        'print(f"Transformers version: {transformers.__version__}")',
        'print(f"Datasets version: {datasets.__version__}")',
        'print(f"Accelerate version: {accelerate.__version__}")',
        'print(f"CUDA available: {torch.cuda.is_available()}")',
        'print(f"PyTorch CUDA version: {torch.version.cuda}")',
        'if torch.cuda.is_available():',
        '    print(f"GPU name: {torch.cuda.get_device_name(0)}")',
        '    device = torch.device("cuda:0")',
        '    a = torch.randn((1024, 1024), device=device)',
        '    b = torch.randn((1024, 1024), device=device)',
        '    c = a @ b',
        '    torch.cuda.synchronize()',
        '    assert c.is_cuda',
        '    print(f"Tensor device: {c.device}")',
        '    print("GPU test: PASS")'
    ) -join [Environment]::NewLine
    Invoke-Checked -FilePath $VenvPython -Arguments @("-c", $VerificationCode)

    $CudaStatusArguments = @("-c", "import torch; print(torch.cuda.is_available())")
    $CudaStatus = (& $VenvPython @CudaStatusArguments | Select-Object -First 1).Trim()
    if ($LASTEXITCODE -ne 0) {
        throw "无法读取 PyTorch CUDA 状态。"
    }
    if ($CudaStatus -eq "True") {
        Write-Host "CUDA 可用。"
    } else {
        Write-Warning "PyTorch 已成功安装，但当前环境未检测到可用 CUDA。正式模型训练前需要进一步确认 PyTorch CUDA wheel、NVIDIA 驱动及本机兼容性。"
    }

    $Nvcc = Get-Command nvcc -ErrorAction SilentlyContinue
    if ($null -ne $Nvcc) {
        Write-Host "nvcc 检测结果（仅作诊断，不决定 PyTorch CUDA runtime）："
        & nvcc --version
        if ($LASTEXITCODE -ne 0) { throw "nvcc 存在但执行失败。" }
    } else {
        Write-Host "未检测到 CUDA Toolkit / nvcc；PyTorch pip CUDA wheel 通常自带所需 CUDA Runtime，因此这不阻止 GPU PyTorch 安装。"
    }
    if ($null -ne $NvidiaSmi) {
        Write-Host "nvidia-smi 检测结果（驱动支持能力不等于 PyTorch CUDA runtime）："
        & nvidia-smi --query-gpu=name,driver_version --format=csv,noheader
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "nvidia-smi 执行失败；这不影响基础 Python 环境验证。"
        }
    } else {
        Write-Host "未检测到 nvidia-smi；这不影响基础 Python 环境验证。"
    }

    Write-Host "B 离线训练 Python 环境配置完成。"
    Write-Host "如需手动激活，可执行：$VenvDirectory\\Scripts\\Activate.ps1"
    exit 0
} catch {
    Write-Error "B 离线训练 Python 环境配置失败：$($_.Exception.Message)"
    exit 1
}
