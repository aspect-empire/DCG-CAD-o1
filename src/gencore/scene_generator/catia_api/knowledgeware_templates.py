from __future__ import annotations

from pathlib import Path
from typing import Any

from .catia_session import CatiaSession


def open_template(template_path: str | Path, session: CatiaSession | None = None):
    session = session or CatiaSession()
    return session.open_document(template_path)


def set_parameter(part, parameter_name: str, value: Any) -> None:
    params = part.parameters
    parameter = params.item(parameter_name)
    try:
        parameter.value = value
    except Exception:
        parameter.valuate_from_string(str(value))


def update_part(part) -> None:
    part.update()


def instantiate_equipment(template_path: str | Path, parameters: dict[str, Any], transform: dict[str, Any] | None = None):
    doc = open_template(template_path)
    part = doc.part
    for name, value in parameters.items():
        set_parameter(part, name, value)
    update_part(part)
    try:
        part.name = transform.get("name", part.name) if transform else part.name
    except Exception:
        pass
    return doc
