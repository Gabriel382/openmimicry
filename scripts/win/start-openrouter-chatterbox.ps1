$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $repoRoot

if (Test-Path ".env") {
    Get-Content ".env" | ForEach-Object {
        if ($_ -match '^\s*([^#=][^=]*)=(.*)$') {
            $name = $Matches[1].Trim()
            $value = $Matches[2].Trim().Trim('"').Trim("'")
            [Environment]::SetEnvironmentVariable($name, $value, "Process")
        }
    }
}

if ([string]::IsNullOrWhiteSpace($env:OPENROUTER_API_KEY)) {
    throw "OPENROUTER_API_KEY is missing. Copy .env.example to .env and add your key."
}

$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
$runtimeInstaller = Join-Path $repoRoot "scripts\install_chatterbox_runtime.py"

function Invoke-NativeCapture {
    param([string[]]$Command)

    $executable = $Command[0]
    $arguments = @($Command | Select-Object -Skip 1)
    $previousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $output = & $executable @arguments 2>&1
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousPreference
    }
    return [PSCustomObject]@{
        Success = ($exitCode -eq 0)
        Output = (@($output | ForEach-Object { $_.ToString() }) -join [Environment]::NewLine).Trim()
    }
}

$needsInstall = -not (Test-Path $python)
if (-not $needsInstall) {
    $check = Invoke-NativeCapture -Command @(
        $python,
        $runtimeInstaller,
        "--python",
        $python,
        "--check-only"
    )
    $needsInstall = -not $check.Success
    if ($needsInstall -and -not [string]::IsNullOrWhiteSpace($check.Output)) {
        Write-Host "Chatterbox runtime needs installation or repair:" -ForegroundColor Yellow
        Write-Host $check.Output -ForegroundColor DarkYellow
    }
}

if ($needsInstall) {
    Write-Host "Installing the OpenRouter + Chatterbox profile..." -ForegroundColor Yellow
    & ".\scripts\win\install.bat" "openrouter-chatterbox"
    if ($LASTEXITCODE -ne 0) {
        throw "Chatterbox profile installation failed. Review the installer report above."
    }
}

if (-not (Test-Path $python)) {
    throw "The installer completed without creating .venv\Scripts\python.exe."
}

$check = Invoke-NativeCapture -Command @(
    $python,
    $runtimeInstaller,
    "--python",
    $python,
    "--check-only"
)
if (-not $check.Success) {
    throw "Chatterbox runtime verification failed.`n$($check.Output)"
}
Write-Host $check.Output -ForegroundColor Green

$preflightMarker = Join-Path $HOME ".openmimicry\chatterbox-preflight-v1.6.2.ok"
$forcePreflight = $env:OPENMIMICRY_CHATTERBOX_PREFLIGHT -eq "force"
if ($forcePreflight -or -not (Test-Path $preflightMarker)) {
    Write-Host "Loading and caching Chatterbox Turbo. The first run can take several minutes..." -ForegroundColor Yellow
    $previousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        & $python -u -m openmimicry.voice.workers.chatterbox_job --preflight --device auto
        $preflightExit = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousPreference
    }
    if ($preflightExit -ne 0) {
        throw "Chatterbox model preflight failed. The backend was not started with an unverified runtime."
    }
    New-Item -ItemType Directory -Path (Split-Path $preflightMarker) -Force | Out-Null
    Set-Content -Path $preflightMarker -Value "OpenMimicry v1.6.2 Chatterbox preflight passed" -Encoding UTF8
} else {
    Write-Host "Chatterbox model preflight already passed for v1.6.2." -ForegroundColor Green
}

$backendPort = 8000
if (Get-Command Get-NetTCPConnection -ErrorAction SilentlyContinue) {
    $existingListener = @(
        Get-NetTCPConnection -LocalPort $backendPort -State Listen -ErrorAction SilentlyContinue |
            Select-Object -First 1
    )
    if ($existingListener.Count -gt 0) {
        $ownerPid = $existingListener[0].OwningProcess
        throw "Port $backendPort is already in use by process $ownerPid. Close the old OpenMimicry backend, then run this launcher once."
    }
}

$env:OPENMIMICRY_PROFILE = "openrouter-chatterbox"
$env:OPENMIMICRY__VOICE__TTS__READINESS_TIMEOUT_S = "180"
$env:HF_HUB_DISABLE_SYMLINKS_WARNING = "1"

Write-Host "Starting OpenMimicry with the openrouter-chatterbox profile..." -ForegroundColor Green
& ".\scripts\win\backend.bat" "--no-reload"
