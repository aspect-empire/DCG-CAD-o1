"""Paths to small, redistributable method resources bundled with GenCore."""

from pathlib import Path


def resource_root() -> Path:
    return Path(__file__).resolve().parent


def foundation_resource_root() -> Path:
    return resource_root() / "foundation"


def case_registry_path() -> Path:
    return resource_root() / "cases" / "foundation_templates_v1.json"


def case_matching_weights_path() -> Path:
    return resource_root() / "case_matching" / "foundation_weights_v1.json"


__all__ = [
    "case_matching_weights_path",
    "case_registry_path",
    "foundation_resource_root",
    "resource_root",
]
