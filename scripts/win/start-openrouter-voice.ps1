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
    throw "RealtimeSTT/RealtimeTTS are still unavailable in .venv after installation.`n$($voiceCheck.Output)"
}
Write-Host $voiceCheck.Output -ForegroundColor Green

$env:OPENMIMICRY_PROFILE = "openrouter-voice"
& ".\scripts\win\backend.bat" "--no-reload"
