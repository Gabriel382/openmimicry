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
$voiceImportCheck = Join-Path $repoRoot "scripts\check_voice_imports.py"

if (-not (Test-Path $voiceImportCheck)) {
    throw "Voice import checker is missing: $voiceImportCheck"
}

function Test-VoiceImports {
    param(
        [string]$PythonPath,
        [string]$CheckScript
    )

    # Windows PowerShell turns a native program's stderr into PowerShell error
    # records. With ErrorActionPreference=Stop that used to terminate this
    # launcher before it could inspect LASTEXITCODE or repair the environment.
    $previousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $output = & $PythonPath $CheckScript 2>&1
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousPreference
    }

    $lines = @($output | ForEach-Object { $_.ToString() })
    return [PSCustomObject]@{
        Success = ($exitCode -eq 0)
        Output = ($lines -join [Environment]::NewLine).Trim()
    }
}

$needsVoiceInstall = -not (Test-Path $python)
if (-not $needsVoiceInstall) {
    $voiceCheck = Test-VoiceImports -PythonPath $python -CheckScript $voiceImportCheck
    $needsVoiceInstall = -not $voiceCheck.Success
    if ($needsVoiceInstall -and -not [string]::IsNullOrWhiteSpace($voiceCheck.Output)) {
        Write-Host "Voice import preflight failed; attempting a repair:" -ForegroundColor Yellow
        Write-Host $voiceCheck.Output -ForegroundColor DarkYellow
    }
}

if ($needsVoiceInstall) {
    Write-Host "OpenMimicry voice dependencies are missing; repairing the project .venv..." -ForegroundColor Yellow
    & ".\scripts\win\install.bat" "openrouter-voice"
    if ($LASTEXITCODE -ne 0) {
        throw "Voice dependency installation failed. Review the pip output above."
    }
}

if (-not (Test-Path $python)) {
    throw "The installer completed without creating .venv\Scripts\python.exe."
}

$voiceCheck = Test-VoiceImports -PythonPath $python -CheckScript $voiceImportCheck
if (-not $voiceCheck.Success) {
    throw "Faster-Whisper/Piper isolated voice dependencies are still unavailable after installation.`n$($voiceCheck.Output)"
}
Write-Host $voiceCheck.Output -ForegroundColor Green

$voiceModel = "en_US-lessac-medium"
$voiceDir = Join-Path $HOME ".openmimicry\voices"
$voiceFile = Join-Path $voiceDir "$voiceModel.onnx"
$voiceConfigFile = Join-Path $voiceDir "$voiceModel.onnx.json"
if (-not (Test-Path $voiceFile) -or -not (Test-Path $voiceConfigFile)) {
    New-Item -ItemType Directory -Path $voiceDir -Force | Out-Null
    Write-Host "Downloading the free Piper voice $voiceModel..." -ForegroundColor Yellow
    & $python -m piper.download_voices --data-dir $voiceDir $voiceModel
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $voiceFile) -or -not (Test-Path $voiceConfigFile)) {
        throw "Piper voice download failed. Expected model and configuration: $voiceFile, $voiceConfigFile"
    }
}

$preflightMarker = Join-Path $HOME ".openmimicry\voice-preflight-v1.5.1.ok"
$forcePreflight = $env:OPENMIMICRY_VOICE_PREFLIGHT -eq "force"
if ($forcePreflight -or -not (Test-Path $preflightMarker)) {
    Write-Host "Running the v1.5.1 voice preflight. The first run downloads and warms medium.en..." -ForegroundColor Yellow
    & $python ".\scripts\voice_doctor.py" --voice $voiceModel --voice-dir $voiceDir --stt-model "medium.en" --turns 3 --playback
    if ($LASTEXITCODE -ne 0) {
        throw "Voice preflight failed. The backend was not started with an unverified audio runtime. Review the JSON report above."
    }
    New-Item -ItemType Directory -Path (Split-Path $preflightMarker) -Force | Out-Null
    Set-Content -Path $preflightMarker -Value "OpenMimicry v1.5.1 voice preflight passed" -Encoding UTF8
} else {
    Write-Host "Voice preflight already passed for v1.5.1. Set OPENMIMICRY_VOICE_PREFLIGHT=force to rerun it." -ForegroundColor Green
}

$backendPort = 8000
if (Get-Command Get-NetTCPConnection -ErrorAction SilentlyContinue) {
    $existingListener = @(
        Get-NetTCPConnection -LocalPort $backendPort -State Listen -ErrorAction SilentlyContinue |
            Select-Object -First 1
    )
    if ($existingListener.Count -gt 0) {
        $ownerPid = $existingListener[0].OwningProcess
        throw "Port $backendPort is already in use by process $ownerPid. Close the old OpenMimicry backend (Ctrl+C in its PowerShell window), then run this launcher once."
    }
}

$env:OPENMIMICRY_PROFILE = "openrouter-voice"
& ".\scripts\win\backend.bat" "--no-reload"
