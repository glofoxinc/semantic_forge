from __future__ import annotations

import json
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> dict | list:
    with path.open(encoding="utf-8-sig") as f:
        return json.load(f)


def save_json(path: Path, data: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def load_defaults() -> dict:
    return load_json(AGENT_ROOT / "config" / "defaults.json")


def load_registry() -> dict:
    return load_json(AGENT_ROOT / "registry" / "dashboards.json")


def save_registry(data: dict) -> None:
    save_json(AGENT_ROOT / "registry" / "dashboards.json", data)


def load_known_mappings() -> dict:
    return load_json(AGENT_ROOT / "registry" / "known_mappings.json")


def slugify(name: str) -> str:
    s = name.lower().strip()
    for ch in " -./\\":
        s = s.replace(ch, "_")
    while "__" in s:
        s = s.replace("__", "_")
    return s.strip("_")
