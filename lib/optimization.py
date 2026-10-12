"""Unified semantic model optimization checklist (PBIP / TMDL)."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Literal

from .classifier import classify_all
from .migration_planner import plan_agg_to_flat
from .pipeline import run_analyze, run_validate
from .tmdl_parser import parse_model

ValidationMode = Literal["wiring", "migration_strict"]

DIVIDE_NO_BLANK_RE = re.compile(r"divide\s*\([^)]+\)", re.IGNORECASE)
MEASURE_BLOCK_RE = re.compile(
    r"\tmeasure\s+(?:'([^']+)'|(\S+))\s*=\s*(.+?)(?=\n\t(?:measure|column|partition|\Z))",
    re.DOTALL,
)
PROPERTY_RE = re.compile(r'"Property"\s*:\s*"([^"]+)"')


def _collect_report_measures(report_path: Path) -> set[str]:
    pages_root = report_path / "definition" / "pages"
    found: set[str] = set()
    if not pages_root.is_dir():
        return found
    for vf in pages_root.rglob("visual.json"):
        blob = vf.read_text(encoding="utf-8-sig")
        found.update(PROPERTY_RE.findall(blob))
    return found


def _scan_dax_heuristics(model_path: Path) -> list[dict]:
    items: list[dict] = []
    tables_dir = model_path / "definition" / "tables"
    if not tables_dir.is_dir():
        return items
    for tmdl in sorted(tables_dir.glob("*.tmdl")):
        text = tmdl.read_text(encoding="utf-8")
        for m in MEASURE_BLOCK_RE.finditer(text):
            name = m.group(1) or m.group(2)
            body = m.group(3)
            if DIVIDE_NO_BLANK_RE.search(body) and "blank()" not in body.lower():
                items.append(
                    {
                        "category": "dax",
                        "priority": "medium",
                        "title": f"Measure '{name}' uses DIVIDE without explicit BLANK handling",
                        "fix_steps": [
                            f"Review measure '{name}' in {tmdl.name}",
                            "Prefer DIVIDE(n, d, BLANK()) or IF(ISBLANK(d), BLANK(), ...)",
                        ],
                        "table": tmdl.stem,
                    }
                )
    return items


def build_optimization_report(
    model_path: Path,
    report_path: Path | None = None,
    *,
    mode: ValidationMode = "wiring",
    direction: str = "agg_to_flat",
) -> dict:
    model_path = model_path.resolve()
    inv = parse_model(model_path)
    analysis = run_analyze(model_path)
    validation = (
        run_validate(model_path, report_path, mode=mode)
        if report_path
        else {
            "passed": True,
            "orphan_count": 0,
            "critical_orphan_count": 0,
            "aggregate_table_count": sum(
                1 for t in analysis["tables"] if t["layer"] == "aggregate"
            ),
            "resolutions": [],
            "errors": [],
        }
    )

    report_scan = None
    if report_path:
        from .pbip_scanner import scan_report

        report_scan = scan_report(report_path)
    plan = plan_agg_to_flat(model_path, report_scan, direction)

    items: list[dict] = []
    seq = 0

    def add(category: str, priority: str, title: str, fix_steps: list[str], **extra: object) -> None:
        nonlocal seq
        seq += 1
        items.append(
            {
                "id": f"OPT-{seq:04d}",
                "category": category,
                "priority": priority,
                "title": title,
                "fix_steps": fix_steps,
                "auto_apply": False,
                **extra,
            }
        )

    for res in validation.get("resolutions", []):
        if res.get("severity") not in ("critical", "medium", "low"):
            continue
        steps = res.get("fix_steps") or []
        if not steps:
            continue
        add(
            "report_wiring",
            res["severity"] if res["severity"] != "low" else "medium",
            f"Orphan entity '{res['entity']}' ({res.get('resolution_type', 'unknown')})",
            steps,
            entity=res["entity"],
            target_table=res.get("target_table"),
        )

    for t in analysis["tables"]:
        if t["layer"] == "aggregate":
            add(
                "model_structure",
                "high",
                f"Replace aggregate table '{t['table']}' with flat lakehouse source",
                [
                    f"Classified as aggregate: {t['reason']}",
                    "Add partition pointing at gold_layer fact/dim; update report bindings if needed",
                ],
                table=t["table"],
            )
        elif t["layer"] == "unknown":
            add(
                "model_structure",
                "medium",
                f"Manually classify table '{t['table']}'",
                [t["reason"], "Update classification defaults or known_mappings if corp-specific"],
                table=t["table"],
            )

    for action in plan.get("actions", []):
        if action.get("action") == "fix_orphan_visual":
            continue
        if action.get("priority") not in ("critical", "high", "medium"):
            continue
        hint = action.get("m_query_hint")
        steps = [action.get("reason", "Migration action")]
        if hint:
            steps.append(f"M partition hint: {hint}")
        add(
            "migration",
            action.get("priority", "medium"),
            f"{action.get('action')}: {action.get('source_table')} -> {action.get('target_table')}",
            steps,
            source_table=action.get("source_table"),
            target_table=action.get("target_table"),
        )

    for dax in _scan_dax_heuristics(model_path):
        add(dax["category"], dax["priority"], dax["title"], dax["fix_steps"], table=dax.get("table"))

    if report_path:
        used = _collect_report_measures(report_path)
        unused = sorted(m for m in set(inv.all_measures) - used if not m.startswith("_"))
        if unused:
            sample = ", ".join(unused[:8])
            suffix = f" (and {len(unused) - 8} more)" if len(unused) > 8 else ""
            add(
                "measures",
                "low",
                f"{len(unused)} measure(s) not referenced in this report",
                [
                    f"Review cleanup candidates: {sample}{suffix}",
                    "Export full list from Doctor Measure Killer or re-run with measure audit",
                ],
                unused_count=len(unused),
                unused_sample=unused[:25],
            )

    critical = sum(1 for i in items if i["priority"] == "critical")
    high = sum(1 for i in items if i["priority"] == "high")
    medium = sum(1 for i in items if i["priority"] == "medium")
    low = sum(1 for i in items if i["priority"] == "low")

    blockers = critical + (high if mode == "migration_strict" else 0)
    if mode == "wiring":
        wiring_pass = validation.get("critical_orphan_count", 0) == 0
    else:
        wiring_pass = validation.get("passed", False)

    score = 100
    score -= min(critical * 25, 50)
    score -= min(high * 5, 25)
    if not wiring_pass:
        score -= 15
    score -= min(medium, 12)
    score = max(0, min(100, score))

    return {
        "engine": "semantic-forge",
        "engine_version": "1.0.0",
        "model_path": str(model_path),
        "report_path": str(report_path) if report_path else None,
        "validation_mode": mode,
        "summary": {
            "optimization_score": score,
            "total_items": len(items),
            "critical": critical,
            "high": high,
            "medium": medium,
            "low": low,
            "release_ready": score >= 80 and wiring_pass and critical == 0,
            "wiring_pass": wiring_pass,
        },
        "validation": {
            "passed": validation.get("passed"),
            "critical_orphans": validation.get("critical_orphan_count", 0),
            "aggregate_tables": validation.get("aggregate_table_count", 0),
        },
        "analysis": {
            "table_count": analysis["table_count"],
            "measure_count": analysis["measures"],
        },
        "items": sorted(
            items,
            key=lambda x: {"critical": 0, "high": 1, "medium": 2, "low": 3}[x["priority"]],
        ),
        "next_actions": [i["fix_steps"][0] for i in items[:10] if i.get("fix_steps")],
        "disclaimer": (
            "Structural + heuristic optimizations only. For full BPA/DAX governance, "
            "run Power BI Doctor or DeskGuard and merge findings."
        ),
    }


def save_optimization_report(out_path: Path, report: dict) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
