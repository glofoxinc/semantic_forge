#!/usr/bin/env python3
"""MCP server — Semantic Forge v1.0.0 (stdio, mcp SDK 2.x)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mcp.server.mcpserver import MCPServer

from lib.optimization import build_optimization_report, save_optimization_report
from lib.paths import AGENT_ROOT, load_json, load_registry
from lib.pipeline import run_analyze, run_e2e, run_plan, run_validate

mcp = MCPServer("semantic-forge")


def _manifest(slug: str) -> dict:
    return load_json(AGENT_ROOT / "dashboards" / slug / "manifest.json")


@mcp.tool()
def list_dashboards() -> str:
    """List onboarded dashboards in the migrator registry."""
    reg = load_registry()
    return json.dumps(reg.get("dashboards", []), indent=2)


@mcp.tool()
def onboard_dashboard(
    name: str,
    report_path: str,
    model_path: str,
    slug: str | None = None,
    corp_id: str = "corp_Jazzercise",
) -> str:
    """Register a PBIP report + semantic model pair (writes manifest and scan artifacts)."""
    cmd = [
        sys.executable,
        str(ROOT / "tools" / "onboard.py"),
        "--name",
        name,
        "--report",
        report_path,
        "--model",
        model_path,
        "--corp-id",
        corp_id,
    ]
    if slug:
        cmd += ["--slug", slug]
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))
    payload = {
        "ok": proc.returncode == 0,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
        "workspace": str(AGENT_ROOT),
    }
    return json.dumps(payload, indent=2)


@mcp.tool()
def analyze_model(model_path: str) -> str:
    """Classify all tables in a semantic model (aggregate | fact | dimension)."""
    return json.dumps(run_analyze(Path(model_path)), indent=2)


@mcp.tool()
def plan_migration(
    model_path: str,
    direction: str = "agg_to_flat",
    report_path: str | None = None,
) -> str:
    """Generate agg-to-flat or flat-to-agg migration plan."""
    rp = Path(report_path) if report_path else None
    return json.dumps(run_plan(Path(model_path), rp, direction), indent=2)


@mcp.tool()
def validate_dashboard(
    model_path: str,
    report_path: str,
    mode: str = "wiring",
) -> str:
    """
    Validate model/report alignment.
    mode=wiring: pass if no critical orphans (agg tables allowed).
    mode=migration_strict: pass only if no critical orphans and no aggregate tables.
    """
    return json.dumps(run_validate(Path(model_path), Path(report_path), mode=mode), indent=2)


@mcp.tool()
def optimization_report(
    model_path: str,
    report_path: str | None = None,
    mode: str = "wiring",
    save_slug: str | None = None,
) -> str:
    """
    Full optimization checklist: orphans, agg/flat, migration actions, DAX heuristics, unused measures.
    Returns score 0-100 and ordered fix steps. Set save_slug to write dashboards/<slug>/optimization.json.
    """
    mp = Path(model_path)
    rp = Path(report_path) if report_path else None
    report = build_optimization_report(mp, rp, mode=mode)  # type: ignore[arg-type]
    if save_slug:
        out = AGENT_ROOT / "dashboards" / save_slug / "optimization.json"
        save_optimization_report(out, report)
        report["saved_to"] = str(out)
    return json.dumps(report, indent=2)


@mcp.tool()
def run_e2e_pipeline(slug: str, validation_mode: str = "wiring") -> str:
    """Run analyze + plan + validate for an onboarded dashboard; writes e2e_report.json."""
    m = _manifest(slug)
    model_path = Path(m["model_path"])
    report_path = Path(m["report_path"])
    out_dir = AGENT_ROOT / "dashboards" / slug

    analysis = run_analyze(model_path)
    from lib.paths import save_json

    save_json(out_dir / "analysis.json", analysis)
    plan_flat = run_plan(model_path, report_path, "agg_to_flat")
    save_json(out_dir / "plan_agg_to_flat.json", plan_flat)
    validation = run_validate(model_path, report_path, mode=validation_mode)
    save_json(out_dir / "validation.json", validation)
    opt = build_optimization_report(model_path, report_path, mode=validation_mode)  # type: ignore[arg-type]
    save_optimization_report(out_dir / "optimization.json", opt)

    report = {
        "slug": slug,
        "display_name": m.get("display_name"),
        "validation_mode": validation_mode,
        "validation": {
            "passed": validation["passed"],
            "critical_orphans": validation["critical_orphan_count"],
            "aggregate_tables": validation["aggregate_table_count"],
        },
        "optimization_score": opt["summary"]["optimization_score"],
        "release_ready": opt["summary"]["release_ready"],
        "top_fixes": opt["next_actions"][:5],
    }
    save_json(out_dir / "e2e_report.json", report)
    return json.dumps(report, indent=2)


@mcp.tool()
def release_readiness(slug: str) -> str:
    """80+ gate: wiring validation + optimization score + blocker counts."""
    m = _manifest(slug)
    model_path = Path(m["model_path"])
    report_path = Path(m["report_path"])
    opt = build_optimization_report(model_path, report_path, mode="wiring")
    val = run_validate(model_path, report_path, mode="wiring")
    ready = opt["summary"]["release_ready"] and val["passed"]
    return json.dumps(
        {
            "slug": slug,
            "release_ready": ready,
            "optimization_score": opt["summary"]["optimization_score"],
            "threshold": 80,
            "blockers": [
                i["title"]
                for i in opt["items"]
                if i["priority"] in ("critical", "high")
            ][:15],
            "recommended_mcp_flow": [
                "onboard_dashboard",
                "run_e2e_pipeline",
                "optimization_report",
                "apply fixes from items[].fix_steps",
                "release_readiness",
            ],
        },
        indent=2,
    )


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
