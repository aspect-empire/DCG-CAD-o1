from __future__ import annotations

from pathlib import Path


def test_excluded_runtime_content_is_absent() -> None:
    root = Path(__file__).resolve().parents[1]
    forbidden_directories = (
        root / "src" / "gencore" / "experiments",
        root / "workspace",
        root / "outputs",
        root / "demo",
    )
    assert all(not path.exists() for path in forbidden_directories)

    forbidden_names = {
        "live_case_service.py",
        "live_cli.py",
        "live_contracts.py",
        "live_runtime.py",
        "live_tools.py",
        "live_verification.py",
    }
    assert not any(path.name in forbidden_names for path in root.rglob("*.py"))

    forbidden_suffixes = {
        ".sqlite3",
        ".db",
        ".log",
        ".pid",
        ".catpart",
        ".catproduct",
        ".stp",
        ".step",
        ".stl",
    }
    ignored_roots = {".pytest-workbench", ".pytest_cache", "dist", "build"}
    candidates = (
        path
        for path in root.rglob("*")
        if not any(part in ignored_roots for part in path.relative_to(root).parts)
    )
    assert not any(path.suffix.lower() in forbidden_suffixes for path in candidates)
