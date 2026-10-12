# Clone-and-go setup for Semantic Forge
$ErrorActionPreference = "Stop"
$forgeRoot = Split-Path $PSScriptRoot -Parent
$repoRoot = Split-Path $forgeRoot -Parent
Set-Location $forgeRoot
Write-Host "Semantic Forge - setup" -ForegroundColor Cyan
& (Join-Path $forgeRoot "scripts\install.ps1")
& (Join-Path $forgeRoot "scripts\verify.ps1")
$skillSrc = Join-Path $repoRoot "docs\SKILL.md"
if (-not (Test-Path $skillSrc)) { Write-Error "Missing $skillSrc" }
$dest = Join-Path $env:USERPROFILE ".cursor\skills\semantic-forge"
New-Item -ItemType Directory -Force -Path $dest | Out-Null
Copy-Item -Force $skillSrc (Join-Path $dest "SKILL.md")
Write-Host "Installed skill -> $dest" -ForegroundColor Green
Write-Host ""
Write-Host "In Cursor, say:" -ForegroundColor Yellow
Write-Host '  "Setup Semantic Forge"'
Write-Host ""
Write-Host "Full guide: $repoRoot\DOCUMENTATION.html" -ForegroundColor Cyan
