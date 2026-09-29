from __future__ import annotations

import json
from pathlib import Path

from examples.basic_case.run import run_example


def test_basic_case_matches_expected_summary(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1] / "examples" / "basic_case"
    expected = json.loads((root / "expected_summary.json").read_text(encoding="utf-8"))
    assert run_example(tmp_path) == expected
