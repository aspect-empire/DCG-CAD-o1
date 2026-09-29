"""Run and verify the synthetic GenCore example offline."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from gencore.orchestration import replay_fixture


def run_example(output_root: str | Path) -> dict[str, object]:
    root = Path(__file__).resolve().parent
    result = replay_fixture(
        root / "input.json",
        root / "scripted_outcomes.json",
        output_root,
    )
    return result.semantic_summary()


def main() -> int:
    root = Path(__file__).resolve().parent
    expected = json.loads((root / "expected_summary.json").read_text(encoding="utf-8"))
    with TemporaryDirectory(prefix="gencore-basic-") as output_root:
        actual = run_example(output_root)
    print(json.dumps(actual, ensure_ascii=False, indent=2))
    if actual != expected:
        print("The actual summary does not match expected_summary.json.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
