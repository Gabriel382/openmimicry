<#
.SYNOPSIS
    OpenMimicry v1.0 — one-shot legacy-tree cleanup (PowerShell).

.DESCRIPTION
    Removes the prototype directories superseded by the new
    `packages/` and `apps/` layout, plus dev caches and stale
    milestone notes. Re-runnable; missing paths are silently
    skipped.

.PARAMETER Apply
    When set, actually deletes the paths. Without this switch the
    script prints a dry-run list.

.EXAMPLE
    PS> .\scripts\cleanup-legacy.ps1               # dry run
    PS> .\scripts\cleanup-legacy.ps1 -Apply        # delete

#>

[CmdletBinding()]
param(
    [switch]$Apply
)

$ErrorActionPreference = 'Stop'

$legacyDirs = @(
    'avatar', 'backend', 'backends', 'core', 'frontend',
    'src-tauri', 'tts', 'packs', 'profiles'
)

$cacheDirs = @(
    'node_modules', 'openmimicry.egg-info',
    '.pytest_cache', '.ruff_cache', '.venv'
)

$cacheGlobs = @('pytest-cache-files-*')

$staleFiles = @(
    ':USERPROFILE.wslconfig',
    'realtimesst.log',
    'Milestone.md',
    'MILESTONE5_INTEGRATION.md',
    'PATCH_NOTES.md',
    'README_EMOTION_SPEAKING_PATCH.md',
    'README_MILESTONE6.md',
    'README_MILESTONE6_5.md',
    'README_MILESTONE8.md'
)

function Remove-Target {
    param([string]$Path)
    if ($Apply) {
        Write-Host "  rm: $Path"
        Remove-Item -Recurse -Force -LiteralPath $Path -ErrorAction SilentlyContinue
    }
    else {
        Write-Host "  would rm: $Path"
    }
}

foreach ($d in @($legacyDirs + $cacheDirs)) {
    if (Test-Path -LiteralPath $d) { Remove-Target $d }
}

foreach ($g in $cacheGlobs) {
    Get-ChildItem -Path $g -ErrorAction SilentlyContinue | ForEach-Object {
        Remove-Target $_.FullName
    }
}

foreach ($f in $staleFiles) {
    if (Test-Path -LiteralPath $f) { Remove-Target $f }
}

if (-not $Apply) {
    Write-Host ""
    Write-Host "Dry run. Re-run with -Apply to actually delete."
}
else {
    Write-Host ""
    Write-Host "Cleanup complete. Review with: git status"
}
