---
name: semantic-forge
description: Semantic Forge MCP for Power BI model optimization. Use when the user says setup semantic forge, analyze this model, suggest optimizations, unused tables, unused relationships, unused columns, unused measures, shall we proceed. Setup: run forge/scripts/setup.ps1 and wire MCP from forge/config/cursor-mcp.example.json. Analyze first, write a full Word plan, then STOP and ask shall we proceed with optimization. Only apply if the user says yes.
---

# Semantic Forge

## Setup (about 5 minutes)

When the user says **Setup Semantic Forge**:

1. Run `forge/scripts/setup.ps1` from this clone (do not ask them to run it).
2. Wire MCP from `forge/config/cursor-mcp.example.json` (`<CLONE_PATH>/forge/mcp/server.py`).
3. If Python, a report folder, a model folder, or a login is missing, **ask once** and wait. Do not dump extra steps.
4. Confirm ready: they can say *Analyze this model and suggest optimizations.*

## Analyze (always first)

1. Locate the `.Report` and `.SemanticModel` folders (ask if missing).
2. Run analyze / optimize / e2e via MCP or, from the `forge/` folder, `python tools/run_agent.py`.
3. Cover **all** of: unused tables, unused relationships, unused columns, unused measures, broken report wiring, and other checklist items.
4. Write a **complete Word plan** (`dashboards/<slug>/optimization-plan.docx`) listing every proposed change. Nothing is edited yet.

## Gate (mandatory)

Ask exactly:

**Shall we proceed with optimization?**

- **No** — leave the model unchanged. Keep the Word plan.
- **Yes** — apply the plan carefully, item by item. Do not skip unused tables, relationships, columns, or measures that were listed. Re-scan and report what changed.

Never optimize before that yes.
