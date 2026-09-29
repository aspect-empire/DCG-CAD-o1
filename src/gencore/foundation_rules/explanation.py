"""Deterministic derivation ledger records."""

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class DerivationStep:
    step_id: str
    operation: str
    inputs: tuple[str, ...]
    output: str
    rule_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["inputs"] = list(self.inputs)
        value["rule_ids"] = list(self.rule_ids)
        return value
