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

$env:OPENMIMICRY_PROFILE = "openrouter-voice"
& ".\scripts\win\backend.bat"
