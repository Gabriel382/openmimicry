$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $repoRoot

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$outputDir = Join-Path $repoRoot "diagnostics"
$outputPath = Join-Path $outputDir "OpenMimicry-diagnostics-v1.5.1-$timestamp.zip"
New-Item -ItemType Directory -Force -Path $outputDir | Out-Null

try {
    Invoke-WebRequest `
        -UseBasicParsing `
        -Uri "http://127.0.0.1:8000/diagnostics/bundle" `
        -OutFile $outputPath `
        -TimeoutSec 10
    Write-Host "Downloaded the live diagnostic bundle:" -ForegroundColor Green
    Write-Host $outputPath
    exit 0
}
catch {
    Write-Host "The backend diagnostic endpoint is unavailable; collecting local logs." -ForegroundColor Yellow
}

$staging = Join-Path $env:TEMP "openmimicry-diagnostics-$timestamp"
New-Item -ItemType Directory -Force -Path $staging | Out-Null

$logDir = Join-Path $HOME ".openmimicry\logs"
if (Test-Path $logDir) {
    Copy-Item -Path (Join-Path $logDir "openmimicry-*.log*") -Destination $staging -ErrorAction SilentlyContinue
}

$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (Test-Path $python) {
    & $python --version 2>&1 | Out-File -Encoding utf8 (Join-Path $staging "python-version.txt")
    & $python -m pip show openmimicry-backend openmimicry-core openmimicry-voice faster-whisper piper-tts sounddevice numpy litellm fastapi uvicorn websockets RealtimeSTT RealtimeTTS 2>&1 |
        Out-File -Encoding utf8 (Join-Path $staging "voice-packages.txt")
    & $python (Join-Path $repoRoot "scripts\check_voice_imports.py") 2>&1 |
        Out-File -Encoding utf8 (Join-Path $staging "voice-imports.txt")
}

@"
OpenMimicry fallback diagnostic bundle
Generated: $(Get-Date -Format o)

This archive excludes .env and API-key values. Review paths and transcripts before sharing.
"@ | Out-File -Encoding utf8 (Join-Path $staging "README.txt")

Compress-Archive -Path (Join-Path $staging "*") -DestinationPath $outputPath -Force
Remove-Item -Recurse -Force $staging
Write-Host "Created the fallback diagnostic bundle:" -ForegroundColor Green
Write-Host $outputPath
