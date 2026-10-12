from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path

from .classifier import TableClassification, classify_all
from .entity_resolver import build_entity_index, resolve_orphan
from .paths import load_known_mappings
from .pbip_scanner import find_orphan_details
from .tmdl_parser import ModelInventory, parse_model


@dataclass
class MigrationAction:
    action: str  # replace_agg | keep_flat | fix_orphan_visual | add_relationship
    source_table: str
    target_table: str | None
    priority: str  # critical | high | medium | low
    reason: str
    measure_impact: list[str] = field(default_factory=list)
    m_query_hint: str | None = None


def plan_agg_to_flat(
    model_path: Path,
    report_scan: dict | None = None,
    direction: str = "agg_to_flat",
) -> dict:
    inv = parse_model(model_path)
    classifications = classify_all(inv.tables)
    known = {m["agg_table"]: m for m in load_known_mappings()["mappings"]}
    actions: list[MigrationAction] = []

    agg_tables = [c for c in classifications if c.layer == "aggregate"]
    for c in agg_tables:
        mapping = known.get(c.table.replace(" ", "_"))
        target = c.lakehouse_guess or (mapping["flat_table"] if mapping else None)
        date_col = mapping.get("date_column") if mapping else None
        actions.append(
            MigrationAction(
                action="replace_agg",
                source_table=c.table,
                target_table=target,
                priority="critical" if report_scan and _used_in_report(c.table, report_scan) else "high",
                reason=f"Aggregate table -> flat lakehouse fact/dim ({direction})",
                m_query_hint=_m_query_stub(target, date_col) if target else None,
            )
        )

    flat_inventory: list[dict] = []
    index = build_entity_index(inv)

    if report_scan:
        orphans = find_orphan_details(report_scan, set(inv.tables.keys()))
        for row in orphans:
            res = resolve_orphan(row["entity"], index, inv, row.get("usage", "unknown"))
            priority = res.severity if res.severity in ("critical", "high") else "medium"
            actions.append(
                MigrationAction(
                    action="fix_orphan_visual",
                    source_table=row["entity"],
                    target_table=res.target_table,
                    priority=priority,
                    reason=res.reason,
                    m_query_hint=_m_query_stub(
                        res.target_table if res.target_table and res.target_table.startswith("gold_layer.") else known.get(row["entity"], {}).get("flat_table"),
                        known.get(row["entity"], {}).get("date_column") or res.target_column,
                    ),
                )
            )

    flat_tables = [c for c in classifications if c.layer in ("fact", "dimension")]
    for c in flat_tables:
        src = inv.tables[c.table].lakehouse_source if c.table in inv.tables else None
        if src:
            flat_inventory.append({
                "table": c.table,
                "lakehouse": f"gold_layer.{src}",
                "layer": c.layer,
            })

    return {
        "direction": direction,
        "model": model_path.name,
        "summary": {
            "tables": len(inv.tables),
            "aggregate": len(agg_tables),
            "flat": len(flat_tables),
            "actions": len(actions),
            "critical": sum(1 for a in actions if a.priority == "critical"),
        },
        "classifications": [asdict(c) for c in classifications],
        "actions": [asdict(a) for a in actions],
        "flat_inventory": flat_inventory,
        "relationships_count": len(inv.relationships),
    }


def plan_flat_to_agg(model_path: Path) -> dict:
    """Suggest rollup tables for large fact tables (optimization path)."""
    inv = parse_model(model_path)
    suggestions = []
    for name, info in inv.tables.items():
        if info.lakehouse_source and (
            info.lakehouse_source.startswith("flt_") or info.lakehouse_source.startswith("fct_")
        ):
            agg_name = f"agg_{info.lakehouse_source[4:]}"
            suggestions.append({
                "source_fact": name,
                "lakehouse": f"gold_layer.{info.lakehouse_source}",
                "suggested_agg": agg_name,
                "reason": "Pre-aggregate at daily grain for refresh performance",
                "note": "Only if measures are additive at that grain - validate DAX first",
            })
    return {
        "direction": "flat_to_agg",
        "model": model_path.name,
        "suggestions": suggestions,
    }


def _used_in_report(table: str, report_scan: dict) -> bool:
    for p in report_scan.get("pages", []):
        if table in p.get("entities", []):
            return True
    return table in report_scan.get("all_entities", [])


def _m_query_stub(target: str | None, date_col: str | None) -> str | None:
    if not target:
        return None
    table = target.split(".")[-1]
    date_filter = ""
    if date_col:
        date_filter = f"\nWHERE s.{date_col} >= DATEADD(YEAR,-1,CAST(GETDATE() AS DATE))"
    return (
        f"SELECT s.* FROM gold_layer.{table} AS s\n"
        f"INNER JOIN branches_selected b ON b.id = s.branch_id"
        f"{date_filter}"
    )
