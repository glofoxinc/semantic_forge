# Semantic Forge

Cursor **MCP** for Power BI: analyze a `.SemanticModel` + `.Report`, write a **Word optimization plan**, then apply changes only after you say **yes**.

## Repo layout (3 folders)

| Path | Contents |
|------|----------|
| **`docs/`** | `SKILL.md` (Cursor skill), `SLACK-ANNOUNCE.txt` (team paste template) |
| **`forge/`** | MCP server, Python `lib/`, CLI `tools/`, `config/`, `scripts/`, tests |
| **`.github/`** | CI |

Share files at repo root: `DOCUMENTATION.html`, `share-image.svg`, this `README.md`.

## Quick start

1. Clone and open the repo in **Cursor**.
2. Run `forge/scripts/setup.ps1` once (installs deps + copies `docs/SKILL.md` into your user skills folder).
3. Wire MCP: `forge/config/cursor-mcp.example.json` → point at `<CLONE_PATH>/forge/mcp/server.py`.
4. In chat: **Setup Semantic Forge**, then **Analyse this model and suggest optimizations**.

Pair with **[Semantic Scout](https://github.com/glofoxinc/semantic-scout)** before you raise a PR.
