---
name: semantic-forge
description: Semantic Forge MCP for Power BI model optimization. Use when the user says setup semantic forge, analyze this model, suggest optimizations, unused tables, unused relationships, unused columns, unused measures, shall we proceed. After clone, user says Setup Semantic Forge in Cursor — you handle MCP and skill install; never ask them to run scripts. Analyze first, write a full Word plan, then STOP and ask shall we proceed with optimization. Only apply if the user says yes.
---

# Semantic Forge

## What the user does (only this)

1. Clone **glofoxinc/semantic_forge** and open the repo folder in **Cursor**.
2. Say **Setup Semantic Forge**.
3. If you ask for a report folder, model folder, or a login, they answer **once**.

**Never** tell the user to run PowerShell, `setup.ps1`, pip, or edit MCP JSON themselves.

## Setup — when the user says **Setup Semantic Forge**

You (the agent) do the technical work in chat:

1. Install this skill into `%USERPROFILE%\.cursor\skills\semantic-forge\SKILL.md` from `docs/SKILL.md` in the clone.
2. Wire Cursor MCP to `<clone>/forge/mcp/server.py` (use `forge/config/cursor-mcp.example.json` as the template; substitute the real clone path).
3. Install Python deps from `forge/requirements.txt` if import fails — do not ask the user to run install unless they prefer to.
4. Confirm they can say: *Analyse this report and semantic model. Write the full Word plan.*

## Analyze (always first)

1. Locate the `.Report` and `.SemanticModel` folders (ask if missing).
2. Run analyze / optimize / e2e via MCP or, from the `forge/` folder, `python tools/run_agent.py` (agent-only; do not put this in user setup steps).
3. Cover **all** of: unused tables, unused relationships, unused columns, unused measures, broken report wiring, and other checklist items.
4. Write a **complete Word plan** (`dashboards/<slug>/optimization-plan.docx`) listing every proposed change. Nothing is edited yet.

## Gate (mandatory)

Ask exactly:

**Shall we proceed with optimization?**

- **No** — leave the model unchanged. Keep the Word plan.
- **Yes** — apply the plan carefully, item by item. Do not skip unused tables, relationships, columns, or measures that were listed. Re-scan and report what changed.

Never optimize before that yes.
