from __future__ import annotations

from pathlib import Path
from typing import Iterable


class CatiaSession:
    """Small wrapper around pycatia document lifecycle operations."""

    def __init__(self, visible: bool = True):
        from pycatia import catia

        self.app = catia()
        try:
            self.app.visible = visible
        except Exception:
            pass

    def new_part(self, name: str = "ShipCompartment"):
        doc = self.app.documents.add("Part")
        try:
            doc.part.name = name
        except Exception:
            pass
        return doc

    def new_product(self, name: str = "ShipCompartmentScene"):
        doc = self.app.documents.add("Product")
        try:
            doc.product.part_number = name
        except Exception:
            pass
        return doc

    def open_document(self, path: str | Path):
        return self.app.documents.open(str(Path(path)))

    def save_as(self, doc, path: str | Path) -> Path:
        target = Path(path).expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            target.unlink()
        doc.save_as(str(target))
        return target

    def close(self, doc) -> None:
        doc.close()

    def close_documents_for_paths(self, paths: Iterable[str | Path]) -> None:
        targets = [Path(path).expanduser().resolve() for path in paths]
        target_full_names = {str(path).lower() for path in targets}
        target_names = {path.name.lower() for path in targets}
        docs = self.app.documents.com_object
        for index in range(int(docs.Count), 0, -1):
            try:
                doc = docs.Item(index)
                full_name = str(getattr(doc, "FullName", "") or "")
                name = str(getattr(doc, "Name", "") or "")
                full_key = full_name.lower()
                name_key = name.lower()
                has_real_full_name = bool(full_name) and full_key != name_key
                if full_key in target_full_names or (not has_real_full_name and name_key in target_names):
                    doc.Close()
            except Exception:
                continue

    def update(self, doc) -> None:
        if hasattr(doc, "part"):
            doc.part.update()
        elif hasattr(doc, "product"):
            doc.product.update()
