"""Production smoke tests — parser, registry, bundled sample dashboard."""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "minimal_table.tmdl"


def test_parse_table_file_reads_measures_and_columns():
    from lib.tmdl_parser import parse_table_file

    info = parse_table_file(FIXTURE)
    assert info.name == "Sales"
    assert "Amount" in info.columns
    assert any("Total Sales" in m for m in info.measures)


def test_registry_lists_sample_dashboard():
    from lib.paths import load_registry

    reg = load_registry()
    slugs = {d.get("slug") for d in reg.get("dashboards", [])}
    assert "executive_dashboard" in slugs


def test_sample_dashboard_has_validation_artifact():
    path = ROOT / "dashboards" / "executive_dashboard" / "validation.json"
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "passed" in text or "orphan" in text.lower()


def test_run_agent_list_exits_zero():
    import subprocess
    import sys

    proc = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "run_agent.py"), "list"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
