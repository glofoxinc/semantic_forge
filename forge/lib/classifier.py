from __future__ import annotations

import re
from dataclasses import dataclass

from .paths import load_defaults
from .tmdl_parser import TableInfo


@dataclass
class TableClassification:
    table: str
    layer: str  # aggregate | fact | dimension | measure_table | unknown
    confidence: str  # high | medium | low
    reason: str
    lakehouse_guess: str | None = None


def _any_match(name: str, patterns: list[str]) -> bool:
    return any(re.search(p, name, re.IGNORECASE) for p in patterns)


def classify_table(info: TableInfo) -> TableClassification:
    cfg = load_defaults()["classification"]
    name = info.name

    if name == "All Measures":
        return TableClassification(name, "measure_table", "high", "Central measures table")

    if _any_match(name, cfg["agg_name_patterns"]):
        return TableClassification(
            name, "aggregate", "high", "Name matches aggregate pattern", _guess_flat(name, info)
        )

    if info.lakehouse_source:
        src = info.lakehouse_source
        if src.startswith("agg_") or src.startswith("mv_"):
            return TableClassification(name, "aggregate", "high", f"SQL source {src}", _guess_flat(name, info))
        if src.startswith("dim_"):
            return TableClassification(name, "dimension", "high", f"SQL source {src}", f"gold_layer.{src}")
        if src.startswith("flt_") or src.startswith("fct_"):
            return TableClassification(name, "fact", "high", f"SQL source {src}", f"gold_layer.{src}")

    if _any_match(name, cfg["dim_name_patterns"]):
        return TableClassification(name, "dimension", "medium", "Name matches dimension pattern")

    if _any_match(name, cfg["fact_name_patterns"]):
        return TableClassification(name, "fact", "medium", "Name matches fact pattern")

    # Heuristic: many numeric columns + few keys → possible agg
    numeric_hints = sum(1 for c in info.columns if any(k in c.lower() for k in ("amount", "count", "total", "kpi", "pct", "%")))
    if numeric_hints >= 5 and len(info.columns) < 25:
        return TableClassification(name, "aggregate", "low", "Wide numeric layout suggests pre-aggregation")

    if name.startswith("_"):
        return TableClassification(name, "helper", "medium", "Hidden/calculation helper table")

    return TableClassification(name, "unknown", "low", "Could not classify - manual review")


def _guess_flat(name: str, info: TableInfo) -> str | None:
    from .paths import load_known_mappings

    known = {m["agg_table"]: m["flat_table"] for m in load_known_mappings()["mappings"]}
    key = name.replace(" ", "_").lower()
    for agg, flat in known.items():
        if agg.lower() == key.lower() or agg.lower() in key.lower():
            return flat
    if info.lakehouse_source and not info.lakehouse_source.startswith("agg_"):
        return f"gold_layer.{info.lakehouse_source}"
    # Naming convention: agg_foo_bar → flt_foo_bar
    if name.lower().startswith("agg_"):
        return f"gold_layer.flt_{name[4:].lower()}"
    return None


def classify_all(tables: dict[str, TableInfo]) -> list[TableClassification]:
    return [classify_table(t) for t in tables.values()]
