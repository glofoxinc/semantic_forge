"""Universal report-entity resolution for any PBIP semantic model."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from .paths import load_known_mappings
from .tmdl_parser import ModelInventory, TableInfo

SKIP_DIMS = frozenset({"dim_branch_all", "branches_selected", "dim_user_rls", "wvuserrlsglofox"})
USAGE_QUERY = "query"
USAGE_CONDITIONAL = "conditional_format"
USAGE_UNKNOWN = "unknown"


@dataclass
class OrphanResolution:
    entity: str
    severity: str  # critical | medium | low
    resolution_type: str  # rename_entity | add_table | conditional_format | extension_entity
    target_table: str | None
    target_column: str | None
    confidence: str
    reason: str
    fix_steps: list[str] = field(default_factory=list)
    visuals: list[dict] = field(default_factory=list)


def normalize_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def build_entity_index(inv: ModelInventory) -> dict[str, str]:
    """Map alias (normalized, lakehouse, agg name) -> canonical model table name."""
    index: dict[str, str] = {}
    for table_name, info in inv.tables.items():
        index[table_name] = table_name
        index[normalize_key(table_name)] = table_name
        if info.lakehouse_source:
            src = info.lakehouse_source
            index[src] = table_name
            index[normalize_key(src)] = table_name
    return index


def infer_flat_target(entity: str) -> str | None:
    """Naming-convention guess: agg_foo -> gold_layer.flt_foo."""
    e = entity.strip()
    if e.startswith("agg_"):
        return f"gold_layer.flt_{e[4:]}"
    if e.startswith("flt_") or e.startswith("fct_") or e.startswith("dim_"):
        return f"gold_layer.{e}"
    return None


def resolve_orphan(
    entity: str,
    index: dict[str, str],
    inv: ModelInventory,
    usage: str = USAGE_UNKNOWN,
) -> OrphanResolution:
    known = {m["agg_table"]: m for m in load_known_mappings()["mappings"]}
    mapping = known.get(entity)

    # Direct alias (lakehouse name -> friendly model table name)
    if entity in index and index[entity] != entity:
        target = index[entity]
        return OrphanResolution(
            entity=entity,
            severity="critical" if usage == USAGE_QUERY else "medium",
            resolution_type="rename_entity",
            target_table=target,
            target_column=None,
            confidence="high",
            reason="Report uses lakehouse/alias name; model table has a different display name",
            fix_steps=[f"Rebind report Entity '{entity}' to '{target}'"],
        )

    norm = normalize_key(entity)
    if norm in index:
        return OrphanResolution(
            entity=entity,
            severity="critical" if usage == USAGE_QUERY else "medium",
            resolution_type="rename_entity",
            target_table=index[norm],
            target_column=None,
            confidence="high",
            reason=f"Normalized match to model table '{index[norm]}'",
            fix_steps=[
                f"In Power BI / PBIP JSON, replace Entity '{entity}' with '{index[norm]}'",
                "Or add a query alias in the semantic model (discouraged)",
            ],
        )

    # Known mapping registry
    if mapping:
        if not mapping.get("flat_table"):
            hint = mapping.get("model_table_hint")
            if hint and hint in index:
                return OrphanResolution(
                    entity=entity,
                    severity="critical" if usage == USAGE_QUERY else "low",
                    resolution_type="rename_entity",
                    target_table=index.get(hint, hint),
                    target_column=mapping.get("date_column"),
                    confidence="high",
                    reason=mapping.get("notes", "Registry mapping"),
                    fix_steps=[f"Remap Entity '{entity}' -> '{hint}'"],
                )
            return OrphanResolution(
                entity=entity,
                severity="low",
                resolution_type="conditional_format",
                target_table=None,
                target_column=None,
                confidence="medium",
                reason=mapping.get("notes", "Registry notes only"),
                fix_steps=[
                    "Open affected visuals in Power BI Desktop",
                    "Clear or rebind conditional formatting rules",
                ],
            )
        flat = mapping["flat_table"]
        lake = flat.split(".")[-1]
        target = index.get(lake) or _table_for_lakehouse(inv, lake)
        if target:
            return OrphanResolution(
                entity=entity,
                severity="critical",
                resolution_type="rename_entity",
                target_table=target,
                target_column=mapping.get("date_column"),
                confidence="high",
                reason=mapping.get("notes", "Known agg-to-flat mapping"),
                fix_steps=[
                    f"Remap visual Entity '{entity}' -> '{target}'",
                    f"M-query should source {flat}",
                    "Keep measures on All Measures unchanged when possible",
                ],
            )
        return OrphanResolution(
            entity=entity,
            severity="critical",
            resolution_type="add_table",
            target_table=flat,
            target_column=mapping.get("date_column"),
            confidence="medium",
            reason="Mapped flat table not yet in semantic model",
            fix_steps=[
                f"Add partition importing {flat}",
                f"Relate date column '{mapping.get('date_column')}' to DATE TABLE",
                f"Update report Entity '{entity}' to new table display name",
            ],
        )

    # Stale conditional-format references (common: entity "item")
    if usage == USAGE_CONDITIONAL:
        return OrphanResolution(
            entity=entity,
            severity="low",
            resolution_type="conditional_format",
            target_table=None,
            target_column=None,
            confidence="medium",
            reason="Entity only referenced in conditional formatting / data-point selectors",
            fix_steps=[
                "Open visual in Power BI Desktop",
                "Re-apply series colors or remove stale conditional formatting rules",
                "Publish report after save",
            ],
        )

    # Convention guess
    guess_lake = infer_flat_target(entity)
    if guess_lake:
        lake = guess_lake.split(".")[-1]
        target = index.get(lake) or _table_for_lakehouse(inv, lake)
        if target:
            return OrphanResolution(
                entity=entity,
                severity="critical" if usage == USAGE_QUERY else "medium",
                resolution_type="rename_entity",
                target_table=target,
                target_column=None,
                confidence="medium",
                reason=f"Inferred lakehouse table {guess_lake}",
                fix_steps=[f"Remap Entity '{entity}' -> '{target}'"],
            )

    if entity == "item":
        return OrphanResolution(
            entity=entity,
            severity="low",
            resolution_type="conditional_format",
            target_table=None,
            target_column="item profit center name",
            confidence="medium",
            reason="Legacy profit-center table removed; references remain in chart formatting",
            fix_steps=[
                "Visit Analysis visuals: clear conditional formatting on series",
                "If profit center slicer needed, add dim column to Visits and rebind",
            ],
        )

    return OrphanResolution(
        entity=entity,
        severity="critical" if usage == USAGE_QUERY else "medium",
        resolution_type="add_table",
        target_table=guess_lake,
        target_column=None,
        confidence="low",
        reason="No model table or mapping found",
        fix_steps=[
            f"Add entity '{entity}' to semantic model OR remove from report",
            "Extend registry/known_mappings.json if this is a standard agg table",
        ],
    )


def resolve_all_orphans(
    orphans: list[dict],
    inv: ModelInventory,
) -> list[OrphanResolution]:
    index = build_entity_index(inv)
    seen: set[str] = set()
    out: list[OrphanResolution] = []
    for row in orphans:
        ent = row["entity"]
        if ent in seen:
            continue
        seen.add(ent)
        res = resolve_orphan(ent, index, inv, row.get("usage", USAGE_UNKNOWN))
        res.visuals = row.get("visuals", [])
        out.append(res)
    return out


def resolutions_to_dict(resolutions: list[OrphanResolution]) -> list[dict]:
    return [asdict(r) for r in resolutions]


def _table_for_lakehouse(inv: ModelInventory, lakehouse: str) -> str | None:
    for name, info in inv.tables.items():
        if info.lakehouse_source == lakehouse:
            return name
    return None
