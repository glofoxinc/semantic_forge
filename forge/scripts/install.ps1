# Semantic Forge — one-time setup (run from repo root)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "Python not found. Install Python 3.11+ and retry."
}
python -m pip install -r requirements.txt
python -c "from mcp.server.mcpserver import MCPServer; print('OK: MCP SDK ready')"
python tools/run_agent.py list
Write-Host "`nNext: read DOCUMENTATION.md and run onboard + e2e."
