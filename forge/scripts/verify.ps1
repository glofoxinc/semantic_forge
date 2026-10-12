# Semantic Forge v1.0.0 — production verify (run via forge/scripts/setup.ps1)
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

Write-Host "Semantic Forge - verify" -ForegroundColor Cyan

python -m pip install -q -r requirements-dev.txt
python -c "from mcp.server.mcpserver import MCPServer; print('[OK] MCP SDK')"

python -m pytest tests -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

python tools/run_agent.py list
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "Semantic Forge: all checks passed." -ForegroundColor Green
