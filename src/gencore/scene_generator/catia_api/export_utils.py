from __future__ import annotations

from pathlib import Path


def export_document(document, output_path: str | Path, fmt: str | None = None) -> Path:
    target = Path(output_path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target.unlink()
    if fmt:
        document.export_data(str(target), fmt)
    else:
        document.save_as(str(target))
    return target
