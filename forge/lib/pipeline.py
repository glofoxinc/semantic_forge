"""Shared E2E pipeline for CLI and MCP."""
from __future__ import annotations

from pathlib import Path

from .classifier import classify_all
from .entity_resolver import resolve_all_orphans, resolutions_to_dict
from .migration_planner import plan_agg_to_flat, plan_flat_to_agg
from .paths import AGENT_ROOT, save_json
from .pbip_scanner import find_orphan_details, scan_report
from .tmdl_parser import parse_model


def run_analyze(model_path: Path) -> dict:
    inv = parse_model(model_path)
    classes = classify_all(inv.tables)
    return {
        "tables": [c.__dict__ for c in classes],
        "relationships": len(inv.relationships),
        "measures": len(inv.all_measures),
        "table_count": len(inv.tables),
    }


def run_plan(model_path: Path, report_path: Path | None, direction: str) -> dict:
    report_scan = scan_report(report_path) if report_path else None
    if direction == "flat_to_agg":
        return plan_flat_to_agg(model_path)
    return plan_agg_to_flat(model_path, report_scan, direction)


def run_validate(
    model_path: Path,
    report_path: Path,
    *,
    mode: str = "wiring",
) -> dict:
    inv = parse_model(model_path)
    scan = scan_report(report_path)
    model_tables = set(inv.tables.keys())
    orphan_details = find_orphan_details(scan, model_tables)
    resolutions = resolve_all_orphans(orphan_details, inv)
    aggs = [c for c in classify_all(inv.tables) if c.layer == "aggregate"]

    critical_orphans = [r for r in resolutions if r.severity == "critical"]
    query_orphans = [o for o in orphan_details if o["usage"] == "query"]

    if mode == "migration_strict":
        passed = not critical_orphans and not aggs
    else:
        passed = not critical_orphans
    return {
        "passed": passed,
        "validation_mode": mode,
        "display_name": model_path.name,
        "orphan_count": len(orphan_details),
        "query_orphan_count": len(query_orphans),
        "critical_orphan_count": len(critical_orphans),
        "aggregate_table_count": len(aggs),
        "orphans": orphan_details,
        "resolutions": resolutions_to_dict(resolutions),
        "aggregate_tables": [c.table for c in aggs],
        "errors": _validation_errors(critical_orphans, aggs, orphan_details),
    }


def run_e2e(slug: str) -> dict:
    from .paths import load_json

    manifest = load_json(AGENT_ROOT / "dashboards" / slug / "manifest.json")
    model_path = Path(manifest["model_path"])
    report_path = Path(manifest["report_path"])
    out_dir = AGENT_ROOT / "dashboards" / slug

    analysis = run_analyze(model_path)
    save_json(out_dir / "analysis.json", analysis)

    plan_flat = run_plan(model_path, report_path, "agg_to_flat")
    save_json(out_dir / "plan_agg_to_flat.json", plan_flat)

    validation = run_validate(model_path, report_path)
    save_json(out_dir / "validation.json", validation)

    report = {
        "slug": slug,
        "display_name": manifest.get("display_name"),
        "analysis_summary": {
            "tables": analysis["table_count"],
            "aggregate": sum(1 for t in analysis["tables"] if t["layer"] == "aggregate"),
            "unknown": sum(1 for t in analysis["tables"] if t["layer"] == "unknown"),
        },
        "plan_summary": plan_flat.get("summary", {}),
        "validation": {
            "passed": validation["passed"],
            "critical_orphans": validation["critical_orphan_count"],
            "aggregate_tables": validation["aggregate_table_count"],
        },
        "next_steps": _next_steps(validation),
    }
    save_json(out_dir / "e2e_report.json", report)
    return report


def _validation_errors(critical_orphans, aggs, orphan_details) -> list[str]:
    errors: list[str] = []
    if critical_orphans:
        names = ", ".join(r.entity for r in critical_orphans[:5])
        errors.append(f"{len(critical_orphans)} critical orphan entities: {names}")
    if aggs:
        errors.append(f"{len(aggs)} aggregate tables still in model")
    low_only = [o for o in orphan_details if o["usage"] == "conditional_format"]
    if low_only and not critical_orphans:
        errors.append(f"{len(low_only)} conditional-format-only orphans (low severity)")
    return errors


def _next_steps(validation: dict) -> list[str]:
    steps: list[str] = []
    for res in validation.get("resolutions", []):
        if res.get("severity") == "critical" and res.get("fix_steps"):
            steps.append(f"{res['entity']}: {res['fix_steps'][0]}")
    if validation.get("aggregate_table_count"):
        steps.append("Replace remaining agg_ tables with flat lakehouse partitions")
    if validation.get("passed"):
        steps.append("PASS - publish semantic model + report and run kpi-forge validate")
    return steps[:10]
