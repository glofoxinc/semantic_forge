#!/usr/bin/env python3
r"""
Semantic Forge — universal agg <-> flat semantic model tooling (CLI).

  python tools/run_agent.py list
  python tools/run_agent.py onboard --name "..." --report ".../.Report" --model ".../.SemanticModel"
  python tools/run_agent.py analyze executive_dashboard
  python tools/run_agent.py plan executive_dashboard --direction agg_to_flat
  python tools/run_agent.py validate executive_dashboard
  python tools/run_agent.py remediate executive_dashboard
  python tools/run_agent.py e2e executive_dashboard
  python tools/run_agent.py optimize executive_dashboard
  python tools/run_agent.py mcp
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

TOOLS = Path(__file__).parent
ROOT = TOOLS.parent

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.console import safe_print


def dash_manifest(slug: str) -> dict:
    from lib.paths import load_json

    return load_json(ROOT / "dashboards" / slug / "manifest.json")


def cmd_list() -> int:
    from lib.paths import load_registry

    reg = load_registry()
    dashboards = reg.get("dashboards", [])
    safe_print(f"Semantic Forge v1.0.0 — {len(dashboards)} dashboard(s)\n")
    for d in dashboards:
        safe_print(f"  [{d['slug']}] {d['display_name']}")
    if not dashboards:
        safe_print("  (none - run: onboard --name ... --report ... --model ...)")
    return 0


def cmd_analyze(slug: str) -> int:
    from lib.pipeline import run_analyze
    from lib.paths import save_json

    m = dash_manifest(slug)
    analysis = run_analyze(Path(m["model_path"]))
    out = ROOT / "dashboards" / slug / "analysis.json"
    save_json(out, analysis)
    safe_print(f"Analyzed {analysis['table_count']} tables -> {out}")
    for t in analysis["tables"]:
        if t["layer"] in ("aggregate", "unknown"):
            safe_print(f"  [{t['layer']:10}] {t['table']} - {t['reason']}")
    return 0


def cmd_plan(slug: str, direction: str) -> int:
    from lib.pipeline import run_plan
    from lib.paths import save_json

    m = dash_manifest(slug)
    plan = run_plan(Path(m["model_path"]), Path(m["report_path"]), direction)
    out = ROOT / "dashboards" / slug / f"plan_{direction}.json"
    save_json(out, plan)
    safe_print(f"Plan ({direction}) -> {out}")
    safe_print(f"  Actions: {plan.get('summary', {}).get('actions', 0)}")
    for a in plan.get("actions", [])[:20]:
        if a.get("priority") in ("critical", "high", "medium"):
            target = a.get("target_table") or "?"
            safe_print(f"  [{a['priority']}] {a['action']}: {a['source_table']} -> {target}")
    return 0


def cmd_validate(slug: str) -> int:
    from lib.pipeline import run_validate
    from lib.paths import save_json

    m = dash_manifest(slug)
    result = run_validate(Path(m["model_path"]), Path(m["report_path"]))
    save_json(ROOT / "dashboards" / slug / "validation.json", result)

    safe_print(f"Validate: {m['display_name']}")
    safe_print(f"  Orphan entities: {result['orphan_count']} (query: {result['query_orphan_count']})")
    safe_print(f"  Critical orphans: {result['critical_orphan_count']}")
    safe_print(f"  Aggregate tables: {result['aggregate_table_count']}")

    if result["errors"]:
        safe_print("\nStatus:")
        for e in result["errors"]:
            safe_print(f"  - {e}")
    if result["passed"]:
        safe_print("\nPASS: model aligned with report")
        return 0
    safe_print("\nWARN: review validation.json remediations")
    return 1 if result["critical_orphan_count"] or result["aggregate_table_count"] else 0


def cmd_remediate(slug: str) -> int:
    from lib.pipeline import run_validate
    from lib.paths import save_json

    m = dash_manifest(slug)
    result = run_validate(Path(m["model_path"]), Path(m["report_path"]))
    out = ROOT / "dashboards" / slug / "remediation.json"
    remediation = {
        "slug": slug,
        "resolutions": result["resolutions"],
        "next_steps": [r["fix_steps"][0] for r in result["resolutions"] if r.get("fix_steps")],
    }
    save_json(out, remediation)
    safe_print(f"Remediation plan -> {out}\n")
    for r in result["resolutions"]:
        safe_print(f"[{r['severity']}] {r['entity']}")
        safe_print(f"  type: {r['resolution_type']} | target: {r.get('target_table')}")
        for step in r.get("fix_steps", [])[:2]:
            safe_print(f"  - {step}")
    return 0


def cmd_optimize(slug: str, mode: str) -> int:
    from lib.optimization import build_optimization_report, save_optimization_report

    m = dash_manifest(slug)
    model_path = Path(m["model_path"])
    report_path = Path(m["report_path"])
    report = build_optimization_report(model_path, report_path, mode=mode)  # type: ignore[arg-type]
    out = ROOT / "dashboards" / slug / "optimization.json"
    save_optimization_report(out, report)
    safe_print(f"Optimization score: {report['summary']['optimization_score']}/100")
    safe_print(f"  Items: {report['summary']['total_items']} (critical={report['summary']['critical']})")
    safe_print(f"  Release ready: {report['summary']['release_ready']}")
    safe_print(f"  Report -> {out}")
    for step in report.get("next_actions", [])[:5]:
        safe_print(f"  -> {step}")
    return 0 if report["summary"]["release_ready"] else 1


def cmd_e2e(slug: str) -> int:
    from lib.pipeline import run_e2e

    report = run_e2e(slug)
    safe_print(f"E2E complete: {slug}")
    safe_print(f"  validation passed: {report['validation']['passed']}")
    safe_print(f"  critical orphans: {report['validation']['critical_orphans']}")
    safe_print(f"  report: {ROOT / 'dashboards' / slug / 'e2e_report.json'}")
    for step in report.get("next_steps", [])[:5]:
        safe_print(f"  -> {step}")
    return 0 if report["validation"]["passed"] else 1


def cmd_onboard(args: argparse.Namespace) -> int:
    cmd = [
        sys.executable,
        str(TOOLS / "onboard.py"),
        "--name", args.name,
        "--report", str(args.report),
        "--model", str(args.model),
    ]
    if args.corp_id:
        cmd += ["--corp-id", args.corp_id]
    if args.slug:
        cmd += ["--slug", args.slug]
    return subprocess.call(cmd)


def cmd_mcp() -> int:
    return subprocess.call([sys.executable, str(ROOT / "mcp" / "server.py")])


def main() -> int:
    parser = argparse.ArgumentParser(description="Semantic Forge CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List onboarded dashboards")
    sub.add_parser("mcp", help="Start MCP server (stdio)")

    p_on = sub.add_parser("onboard")
    p_on.add_argument("--name", required=True)
    p_on.add_argument("--report", required=True, type=Path)
    p_on.add_argument("--model", required=True, type=Path)
    p_on.add_argument("--corp-id", default="corp_Jazzercise")
    p_on.add_argument("--slug", default=None)

    p_an = sub.add_parser("analyze")
    p_an.add_argument("dashboard")

    p_pl = sub.add_parser("plan")
    p_pl.add_argument("dashboard")
    p_pl.add_argument("--direction", choices=["agg_to_flat", "flat_to_agg"], default="agg_to_flat")

    p_val = sub.add_parser("validate")
    p_val.add_argument("dashboard")

    p_rem = sub.add_parser("remediate")
    p_rem.add_argument("dashboard")

    p_e2e = sub.add_parser("e2e")
    p_e2e.add_argument("dashboard")

    p_opt = sub.add_parser("optimize", help="Full optimization checklist + score")
    p_opt.add_argument("dashboard")
    p_opt.add_argument(
        "--mode",
        choices=["wiring", "migration_strict"],
        default="wiring",
    )

    args = parser.parse_args()

    if args.command == "list":
        return cmd_list()
    if args.command == "mcp":
        return cmd_mcp()
    if args.command == "onboard":
        return cmd_onboard(args)
    if args.command == "analyze":
        return cmd_analyze(args.dashboard)
    if args.command == "plan":
        return cmd_plan(args.dashboard, args.direction)
    if args.command == "validate":
        return cmd_validate(args.dashboard)
    if args.command == "remediate":
        return cmd_remediate(args.dashboard)
    if args.command == "e2e":
        return cmd_e2e(args.dashboard)
    if args.command == "optimize":
        return cmd_optimize(args.dashboard, args.mode)
    return 1


if __name__ == "__main__":
    sys.exit(main())
