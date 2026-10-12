from __future__ import annotations

import json
import re
from pathlib import Path

ENTITY_RE = re.compile(r'"Entity"\s*:\s*"([^"]+)"')
MEASURE_PROP_RE = re.compile(r'"Property"\s*:\s*"([^"]+)"')
KPI_TYPES = frozenset({"card", "kpi", "multiRowCard", "gauge"})


def _entity_usage(blob: str, entity: str) -> str:
    """Classify whether entity appears in query projections vs formatting only."""
    query_markers = ('"queryRef"', '"projections"', '"prototypeQuery"', '"queryState"')
    cond_markers = ('"dataPoint"', '"selector"', '"scopeId"', '"conditional"')
    has_query = any(m in blob for m in query_markers) and f'"Entity": "{entity}"' in blob
    has_cond = any(m in blob for m in cond_markers) and f'"Entity": "{entity}"' in blob
    if has_query:
        return "query"
    if has_cond:
        return "conditional_format"
    return "unknown"


def scan_report(report_path: Path) -> dict:
    pages_root = report_path / "definition" / "pages"
    pages = []
    orphan_entities: set[str] = set()
    entity_refs: dict[str, list[dict]] = {}

    for page_dir in sorted(pages_root.iterdir()) if pages_root.is_dir() else []:
        if not page_dir.is_dir():
            continue
        page_json = json.loads((page_dir / "page.json").read_text(encoding="utf-8-sig"))
        entities: set[str] = set()
        card_measures: list[str] = []
        visual_count = 0
        page_name = page_json.get("displayName", page_dir.name)

        for vf in (page_dir / "visuals").rglob("visual.json"):
            visual_count += 1
            v = json.loads(vf.read_text(encoding="utf-8-sig"))
            blob = json.dumps(v)
            found = set(ENTITY_RE.findall(blob))
            entities.update(found)
            vtype = v.get("visual", {}).get("visualType", "")
            if vtype in KPI_TYPES:
                card_measures.extend(_card_measures(v))
            for ent in found:
                entity_refs.setdefault(ent, []).append({
                    "page": page_name,
                    "page_id": page_json.get("name", page_dir.name),
                    "visual_id": v.get("name", vf.parent.name),
                    "visual_type": vtype,
                    "usage": _entity_usage(blob, ent),
                })

        pages.append({
            "page_id": page_json.get("name", page_dir.name),
            "display_name": page_name,
            "visual_count": visual_count,
            "entities": sorted(entities),
            "kpi_card_measures": sorted(set(card_measures)),
        })
        orphan_entities.update(entities)

    return {
        "report": report_path.name,
        "report_path": str(report_path.resolve()),
        "page_count": len(pages),
        "pages": pages,
        "all_entities": sorted(orphan_entities),
        "entity_refs": entity_refs,
    }


def _card_measures(visual: dict) -> list[str]:
    found: list[str] = []

    def walk(node: object) -> None:
        if isinstance(node, dict):
            m = node.get("Measure")
            if isinstance(m, dict):
                ent = m.get("Expression", {}).get("SourceRef", {}).get("Entity", "")
                prop = m.get("Property", "")
                if ent == "All Measures" and prop:
                    found.append(prop)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for i in node:
                walk(i)

    walk(visual)
    return found


def find_orphan_entities(report_scan: dict, model_tables: set[str]) -> list[str]:
    return [o["entity"] for o in find_orphan_details(report_scan, model_tables)]


def find_orphan_details(report_scan: dict, model_tables: set[str]) -> list[dict]:
    refs = report_scan.get("entity_refs", {})
    report_entities = set(report_scan.get("all_entities", []))
    orphans: list[dict] = []
    for ent in sorted(report_entities):
        if ent in model_tables or ent.startswith("Extension"):
            continue
        visuals = refs.get(ent, [])
        usages = {v.get("usage", "unknown") for v in visuals}
        usage = "query" if "query" in usages else ("conditional_format" if "conditional_format" in usages else "unknown")
        orphans.append({"entity": ent, "usage": usage, "visuals": visuals})
    return orphans
