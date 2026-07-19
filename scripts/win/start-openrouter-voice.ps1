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
$userConfig = Join-Path $repoRoot "config\user.yaml"
if (-not [string]::IsNullOrWhiteSpace($env:OPENMIMICRY_USER_CONFIG)) {
    $configuredUserPath = [Environment]::ExpandEnvironmentVariables(
        $env:OPENMIMICRY_USER_CONFIG
    )
    if ($configuredUserPath -match '^~[\\/](.*)$') {
        $userConfig = Join-Path $HOME $Matches[1]
    } else {
        $userConfig = $configuredUserPath
    }
}
$useChatterbox = (
    (Test-Path $userConfig) -and
    (Select-String -Path $userConfig -Pattern '^\s*adapter:\s*["'']?chatterbox-local["'']?\s*(?:#.*)?$' -Quiet)
)

function Invoke-NativeCapture {
    param([string[]]$Command)

    $executable = $Command[0]
    $arguments = @($Command | Select-Object -Skip 1)
    $previousPreference = $ErrorActionPreference
    try {
        # Windows PowerShell 5.1 wraps native stderr as PowerShell errors.
        # Capture it without letting ErrorActionPreference terminate repair.
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

function Install-VoiceProfile {
    param([string]$Profile)

    Write-Host "Installing or repairing voice profile '$Profile'..." -ForegroundColor Yellow
    & ".\scripts\win\install.bat" $Profile
    if ($LASTEXITCODE -ne 0) {
        throw "Voice profile installation failed for '$Profile'. Review the installer report above."
    }
    if (-not (Test-Path $python)) {
        throw "The installer completed without creating .venv\Scripts\python.exe."
    }
}

if ($useChatterbox) {
    $profile = "openrouter-chatterbox"
    $runtimeInstaller = Join-Path $repoRoot "scripts\install_chatterbox_runtime.py"
    if (-not (Test-Path $runtimeInstaller)) {
        throw "Chatterbox runtime installer is missing: $runtimeInstaller"
    }

    $needsInstall = -not (Test-Path $python)
    if (-not $needsInstall) {
        $runtimeCheck = Invoke-NativeCapture -Command @(
            $python, $runtimeInstaller, "--python", $python, "--check-only"
        )
        $needsInstall = -not $runtimeCheck.Success
        if ($needsInstall -and -not [string]::IsNullOrWhiteSpace($runtimeCheck.Output)) {
            Write-Host "Chatterbox runtime needs repair:" -ForegroundColor Yellow
            Write-Host $runtimeCheck.Output -ForegroundColor DarkYellow
        }
    }
    if ($needsInstall) {
        Install-VoiceProfile -Profile $profile
    }

    $runtimeCheck = Invoke-NativeCapture -Command @(
        $python, $runtimeInstaller, "--python", $python, "--check-only"
    )
    if (-not $runtimeCheck.Success) {
        throw "Chatterbox runtime verification failed after installation.`n$($runtimeCheck.Output)"
    }
    Write-Host $runtimeCheck.Output -ForegroundColor Green

    $preflightMarker = Join-Path $HOME ".openmimicry\chatterbox-preflight-v1.6.4.ok"
    $forcePreflight = $env:OPENMIMICRY_CHATTERBOX_PREFLIGHT -eq "force"
    if ($forcePreflight -or -not (Test-Path $preflightMarker)) {
        Write-Host "Loading and caching Chatterbox Turbo. The first run can take several minutes..." -ForegroundColor Yellow
        $preflight = Invoke-NativeCapture -Command @(
            $python, "-u", "-m", "openmimicry.voice.workers.chatterbox_job",
            "--preflight", "--device", "auto"
        )
        if (-not $preflight.Success) {
            throw "Chatterbox model preflight failed. The backend was not started.`n$($preflight.Output)"
        }
        Write-Host $preflight.Output -ForegroundColor Green
        New-Item -ItemType Directory -Path (Split-Path $preflightMarker) -Force | Out-Null
        Set-Content -Path $preflightMarker -Value "OpenMimicry v1.6.4 Chatterbox preflight passed" -Encoding UTF8
    } else {
        Write-Host "Chatterbox preflight already passed for v1.6.4." -ForegroundColor Green
    }

    $env:OPENMIMICRY__VOICE__TTS__READINESS_TIMEOUT_S = "180"
    $env:HF_HUB_DISABLE_SYMLINKS_WARNING = "1"
} else {
    $profile = "openrouter-voice"
    $voiceImportCheck = Join-Path $repoRoot "scripts\check_voice_imports.py"
    if (-not (Test-Path $voiceImportCheck)) {
        throw "Voice import checker is missing: $voiceImportCheck"
    }

    $needsInstall = -not (Test-Path $python)
    if (-not $needsInstall) {
        $voiceCheck = Invoke-NativeCapture -Command @($python, $voiceImportCheck)
        $needsInstall = -not $voiceCheck.Success
        if ($needsInstall -and -not [string]::IsNullOrWhiteSpace($voiceCheck.Output)) {
            Write-Host "Voice import preflight failed; attempting a repair:" -ForegroundColor Yellow
            Write-Host $voiceCheck.Output -ForegroundColor DarkYellow
        }
    }
    if ($needsInstall) {
        Install-VoiceProfile -Profile $profile
    }

    $voiceCheck = Invoke-NativeCapture -Command @($python, $voiceImportCheck)
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
        Write-Host "Running the voice preflight. The first run downloads and warms medium.en..." -ForegroundColor Yellow
        & $python ".\scripts\voice_doctor.py" --voice $voiceModel --voice-dir $voiceDir --stt-model "medium.en" --turns 3 --playback
        if ($LASTEXITCODE -ne 0) {
            throw "Voice preflight failed. The backend was not started with an unverified audio runtime. Review the JSON report above."
        }
        New-Item -ItemType Directory -Path (Split-Path $preflightMarker) -Force | Out-Null
        Set-Content -Path $preflightMarker -Value "OpenMimicry voice preflight passed" -Encoding UTF8
    } else {
        Write-Host "Voice preflight already passed. Set OPENMIMICRY_VOICE_PREFLIGHT=force to rerun it." -ForegroundColor Green
    }
}

$backendPort = 8000
if (Get-Command Get-NetTCPConnection -ErrorAction SilentlyContinue) {
    $existingListener = @(
        Get-NetTCPConnection -LocalPort $backendPort -State Listen -ErrorAction SilentlyContinue |
            Select-Object -First 1
    )
    if ($existingListener.Count -gt 0) {
        $ownerPid = $existingListener[0].OwningProcess
        throw "Port $backendPort is already in use by process $ownerPid. Close the old OpenMimicry backend (Ctrl+C), then run this launcher once."
    }
}

$env:OPENMIMICRY_PROFILE = $profile
Write-Host "Starting OpenMimicry voice with profile '$profile'..." -ForegroundColor Green
& ".\scripts\win\backend.bat" "--no-reload"
