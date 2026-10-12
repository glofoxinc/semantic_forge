from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

TABLE_RE = re.compile(r"^table\s+(.+)$", re.MULTILINE)
COLUMN_RE = re.compile(r"^\tcolumn\s+(.+)$", re.MULTILINE)
MEASURE_RE = re.compile(
    r"^\tmeasure\s+(?:'([^']+)'|(\S+))\s*=",
    re.MULTILINE,
)
REL_FROM_RE = re.compile(r"^\s*fromColumn:\s*(.+)$", re.MULTILINE)
REL_TO_RE = re.compile(r"^\s*toColumn:\s*(.+)$", re.MULTILINE)
PARTITION_SQL_RE = re.compile(r"FROM\s+gold_layer\.(\w+)", re.IGNORECASE)
LAKEHOUSE_SKIP = frozenset({"dim_branch_all", "branches_selected"})
LAKEHOUSE_PRIORITY = ("flt_", "fct_", "agg_", "dim_date", "dim_")


def _extract_lakehouse_source(text: str) -> str | None:
    matches = PARTITION_SQL_RE.findall(text)
    if not matches:
        return None
    for prefix in LAKEHOUSE_PRIORITY:
        for m in matches:
            if m.startswith(prefix) and m not in LAKEHOUSE_SKIP:
                return m
    for m in reversed(matches):
        if m not in LAKEHOUSE_SKIP:
            return m
    return matches[-1]


@dataclass
class TableInfo:
    name: str
    columns: list[str] = field(default_factory=list)
    measures: list[str] = field(default_factory=list)
    lakehouse_source: str | None = None
    partition_snippet: str = ""


@dataclass
class ModelInventory:
    tables: dict[str, TableInfo]
    relationships: list[dict[str, str]]
    all_measures: list[str]


def _clean_name(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("'") and raw.endswith("'"):
        return raw[1:-1]
    return raw


def parse_table_file(path: Path) -> TableInfo:
    text = path.read_text(encoding="utf-8")
    m = TABLE_RE.search(text)
    name = _clean_name(m.group(1)) if m else path.stem
    cols = [_clean_name(c) for c in COLUMN_RE.findall(text)]
    meas = [m.group(1) or m.group(2) for m in MEASURE_RE.finditer(text)]
    source = _extract_lakehouse_source(text)
    return TableInfo(name=name, columns=cols, measures=meas, lakehouse_source=source, partition_snippet=text[:2000])


def parse_model(model_path: Path) -> ModelInventory:
    tables_dir = model_path / "definition" / "tables"
    tables: dict[str, TableInfo] = {}
    if tables_dir.is_dir():
        for tmdl in sorted(tables_dir.glob("*.tmdl")):
            info = parse_table_file(tmdl)
            tables[info.name] = info

    rels_path = model_path / "definition" / "relationships.tmdl"
    relationships: list[dict[str, str]] = []
    if rels_path.exists():
        lines = rels_path.read_text(encoding="utf-8").splitlines()
        cur: dict[str, str] = {}
        for line in lines:
            if line.startswith("relationship "):
                if cur:
                    relationships.append(cur)
                cur = {}
            fm = REL_FROM_RE.match(line)
            to = REL_TO_RE.match(line)
            if fm:
                cur["from"] = fm.group(1).strip()
            if to:
                cur["to"] = to.group(1).strip()
        if cur:
            relationships.append(cur)

    measures_file = tables_dir / "All Measures.tmdl"
    all_meas: list[str] = []
    if measures_file.exists():
        all_meas = [m.group(1) or m.group(2) for m in MEASURE_RE.finditer(measures_file.read_text(encoding="utf-8"))]

    return ModelInventory(tables=tables, relationships=relationships, all_measures=all_meas)
