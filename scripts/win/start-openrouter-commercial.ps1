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

$venvRoot = Join-Path $repoRoot ".venv"
if (-not [string]::IsNullOrWhiteSpace($env:OPENMIMICRY_VENV)) {
    $configuredVenv = [Environment]::ExpandEnvironmentVariables($env:OPENMIMICRY_VENV)
    if (-not [IO.Path]::IsPathRooted($configuredVenv)) {
        $configuredVenv = Join-Path $repoRoot $configuredVenv
    }
    $venvRoot = [IO.Path]::GetFullPath($configuredVenv)
}
$python = Join-Path $venvRoot "Scripts\python.exe"
$check = Join-Path $repoRoot "scripts\check_commercial_voice_imports.py"
if (-not (Test-Path $python)) {
    & ".\scripts\win\install.bat" "openrouter-commercial"
    if ($LASTEXITCODE -ne 0) { throw "Commercial voice installation failed." }
}

$previousPreference = $ErrorActionPreference
try {
    $ErrorActionPreference = "Continue"
    $checkOutput = & $python $check 2>&1
    $checkExit = $LASTEXITCODE
}
finally {
    $ErrorActionPreference = $previousPreference
}
if ($checkExit -ne 0) {
    Write-Host ($checkOutput -join [Environment]::NewLine) -ForegroundColor Yellow
    & ".\scripts\win\install.bat" "openrouter-commercial"
    if ($LASTEXITCODE -ne 0) { throw "Commercial voice dependency repair failed." }
}

$marker = Join-Path $HOME ".openmimicry\voice-preflight-v1.6.0-commercial.ok"
if ($env:OPENMIMICRY_VOICE_PREFLIGHT -eq "force" -or -not (Test-Path $marker)) {
    Write-Host "Running the v1.6 commercial voice preflight (CPU STT + two system voice turns)..." -ForegroundColor Yellow
    & $python ".\scripts\commercial_voice_doctor.py" --stt-model "medium.en" --playback
    if ($LASTEXITCODE -ne 0) { throw "Commercial voice preflight failed; backend not started." }
    New-Item -ItemType Directory -Path (Split-Path $marker) -Force | Out-Null
    Set-Content -Path $marker -Value "OpenMimicry v1.6.0 commercial voice preflight passed" -Encoding UTF8
}

$env:OPENMIMICRY_PROFILE = "openrouter-commercial"
& ".\scripts\win\backend.bat" "--no-reload"
