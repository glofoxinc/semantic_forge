# Clone-and-go setup for Semantic Forge
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root
Write-Host "Semantic Forge - setup" -ForegroundColor Cyan
& (Join-Path $root "scripts\install.ps1")
& (Join-Path $root "scripts\verify.ps1")
$skillSrc = Join-Path $root ".cursor\skills\semantic-forge\SKILL.md"
if (-not (Test-Path $skillSrc)) { Write-Error "Missing $skillSrc" }
$dest = Join-Path $env:USERPROFILE ".cursor\skills\semantic-forge"
New-Item -ItemType Directory -Force -Path $dest | Out-Null
Copy-Item -Force $skillSrc (Join-Path $dest "SKILL.md")
Write-Host "Installed skill -> $dest" -ForegroundColor Green
Write-Host ""
Write-Host "In Cursor, say:" -ForegroundColor Yellow
Write-Host '  "Set up Semantic Forge MCP from this clone (see config/cursor-mcp.example.json)"'
Write-Host ""
Write-Host "Full guide: DOCUMENTATION.md" -ForegroundColor Cyan
