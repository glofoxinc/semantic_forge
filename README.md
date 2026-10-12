# Semantic Forge

Cursor **MCP** for Power BI: analyze a `.SemanticModel` + `.Report`, write a **Word optimization plan**, then apply changes only after you say **yes**.

| Item | Location |
|------|----------|
| Team guide (browser) | [DOCUMENTATION.html](./DOCUMENTATION.html) |
| Share image | [share-image.svg](./share-image.svg) |
| Cursor skill | [SKILL.md](./SKILL.md) (also `.cursor/skills/semantic-forge/` when you clone) |
| MCP server | `mcp/server.py` |
| Setup scripts | `scripts/setup.ps1`, `scripts/install.ps1` |
| Example MCP config | `config/cursor-mcp.example.json` |
| Tests | `pytest` in `tests/` |

## Quick start

1. Clone this repo and open the folder in **Cursor**.
2. In chat: **Setup Semantic Forge** (or run `scripts/setup.ps1` once).
3. Point Cursor MCP at `mcp/server.py` using `config/cursor-mcp.example.json` (replace `<CLONE_PATH>` with your clone path).
4. **Analyze this model and suggest optimizations** — review the Word plan — answer **Shall we proceed with optimization?**

No secrets are required for the stdio MCP. Do not commit `.env`.

Pair with **[Semantic Scout](https://github.com/glofoxinc/semantic-scout)** before you raise a PR.
