"""Typed independent-validation evidence contracts."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping


@dataclass(frozen=True)
class ValidationCheck:
    check_id: str
    kind: str
    required: bool

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ValidationCheck":
        check_id = str(value.get("check_id", ""))
        kind = str(value.get("kind", ""))
        if not check_id or not kind:
            raise ValueError("validation check_id and kind are required")
        return cls(check_id, kind, bool(value.get("required", False)))


@dataclass(frozen=True)
class ValidationFinding:
    check_id: str
    kind: str
    severity: str
    state: str
    affected_uids: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    tool_id: str | None
    model_version: str | None
    recommended_action: str


@dataclass(frozen=True)
class ValidationResult:
    status: str
    findings: tuple[ValidationFinding, ...]
    missing_checks: tuple[str, ...]
    affected_uids: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    coverage: float
    graph_proposals: tuple[Mapping[str, Any], ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "graph_proposals",
            tuple(MappingProxyType(dict(item)) for item in self.graph_proposals),
        )


__all__ = ["ValidationCheck", "ValidationFinding", "ValidationResult"]
