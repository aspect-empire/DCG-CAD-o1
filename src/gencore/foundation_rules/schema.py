"""Validated source-grounded rule records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from gencore.design_state.records import _freeze, _thaw
from gencore.events import canonical_hash


CLASSIFICATIONS = frozenset({"deterministic", "advisory", "verification_required"})
NORMATIVE_STRENGTHS = frozenset({"shall", "should", "may", "informative"})


@dataclass(frozen=True)
class RuleClause:
    rule_id: str
    classification: str
    normative_strength: str
    source_id: str
    locator: str
    inputs: tuple[str, ...]
    expression: Mapping[str, Any] | None

    def __post_init__(self) -> None:
        if not self.rule_id or not self.source_id or not self.locator:
            raise ValueError("rule_id, source_id and locator are required")
        if self.classification not in CLASSIFICATIONS:
            raise ValueError(f"unsupported classification: {self.classification}")
        if self.normative_strength not in NORMATIVE_STRENGTHS:
            raise ValueError(f"unsupported normative_strength: {self.normative_strength}")
        if self.classification == "deterministic" and self.expression is None:
            raise ValueError("deterministic rule requires an expression")
        object.__setattr__(self, "inputs", tuple(self.inputs))
        if self.expression is not None:
            object.__setattr__(self, "expression", _freeze(self.expression))

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "classification": self.classification,
            "normative_strength": self.normative_strength,
            "source_id": self.source_id,
            "locator": self.locator,
            "inputs": list(self.inputs),
            "expression": _thaw(self.expression),
        }

    @property
    def content_hash(self) -> str:
        return self.recompute_hash()

    def recompute_hash(self) -> str:
        return canonical_hash(self.to_dict())
