#!/usr/bin/env python3
"""Onboard a dashboard + semantic model pair into the migrator registry."""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.paths import AGENT_ROOT, load_registry, save_json, save_registry, slugify
from lib.pbip_scanner import scan_report
from lib.tmdl_parser import parse_model


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--slug", default=None)
    parser.add_argument("--corp-id", default="corp_Jazzercise")
    args = parser.parse_args()

    slug = args.slug or slugify(args.name)
    report_path = args.report.resolve()
    model_path = args.model.resolve()
    dash_dir = AGENT_ROOT / "dashboards" / slug
    dash_dir.mkdir(parents=True, exist_ok=True)

    report_scan = scan_report(report_path)
    model_inv = parse_model(model_path)

    save_json(dash_dir / "report_scan.json", report_scan)
    save_json(
        dash_dir / "model_inventory.json",
        {
            "model": model_path.name,
            "model_path": str(model_path),
            "table_count": len(model_inv.tables),
            "tables": [t.name for t in model_inv.tables.values()],
            "measure_count": len(model_inv.all_measures),
            "relationship_count": len(model_inv.relationships),
        },
    )
    save_json(
        dash_dir / "manifest.json",
        {
            "slug": slug,
            "display_name": args.name,
            "corp_id": args.corp_id,
            "report_path": str(report_path),
            "model_path": str(model_path),
            "onboarded_at": str(date.today()),
        },
    )

    reg = load_registry()
    reg["dashboards"] = [d for d in reg.get("dashboards", []) if d.get("slug") != slug]
    reg["dashboards"].append({
        "slug": slug,
        "display_name": args.name,
        "corp_id": args.corp_id,
        "manifest": f"dashboards/{slug}/manifest.json",
    })
    save_registry(reg)

    print(f"Onboarded: {args.name} ({slug})")
    print(f"  Tables: {len(model_inv.tables)} | Pages: {report_scan['page_count']}")
    print(f"  Output: {dash_dir}")


if __name__ == "__main__":
    main()
