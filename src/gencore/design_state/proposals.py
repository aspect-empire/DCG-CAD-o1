"""Immutable graph-change proposal envelopes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from gencore.events import canonical_hash

from .records import _freeze, _thaw


@dataclass(frozen=True)
class GraphOperation:
    kind: str
    target: str
    value: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not self.kind or not self.target:
            raise ValueError("operation kind and target must be non-empty strings")
        object.__setattr__(self, "value", _freeze(self.value))

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "target": self.target, "value": _thaw(self.value)}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "GraphOperation":
        return cls(str(value["kind"]), str(value["target"]), value.get("value", {}))


@dataclass(frozen=True)
class GraphProposal:
    proposal_id: str
    run_id: str
    base_version: str
    read_set: tuple[str, ...]
    write_set: tuple[str, ...]
    operations: tuple[GraphOperation, ...]
    premise_event_ids: tuple[str, ...]
    validation_plan: tuple[str, ...]

    @classmethod
    def create(
        cls,
        run_id: str,
        base_version: str,
        read_set: Sequence[str],
        write_set: Sequence[str],
        operations: Sequence[GraphOperation],
        premise_event_ids: Sequence[str],
        validation_plan: Sequence[str],
    ) -> "GraphProposal":
        if not run_id or not base_version:
            raise ValueError("run_id and base_version must be non-empty strings")
        ordered_reads = tuple(sorted(set(read_set)))
        ordered_writes = tuple(sorted(set(write_set)))
        ordered_premises = tuple(sorted(set(premise_event_ids)))
        operation_tuple = tuple(operations)
        plan_tuple = tuple(validation_plan)
        body = {
            "run_id": run_id,
            "base_version": base_version,
            "read_set": ordered_reads,
            "write_set": ordered_writes,
            "operations": [operation.to_dict() for operation in operation_tuple],
            "premise_event_ids": ordered_premises,
            "validation_plan": plan_tuple,
        }
        return cls(
            "proposal:" + canonical_hash(body),
            run_id,
            base_version,
            ordered_reads,
            ordered_writes,
            operation_tuple,
            ordered_premises,
            plan_tuple,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "run_id": self.run_id,
            "base_version": self.base_version,
            "read_set": list(self.read_set),
            "write_set": list(self.write_set),
            "operations": [operation.to_dict() for operation in self.operations],
            "premise_event_ids": list(self.premise_event_ids),
            "validation_plan": list(self.validation_plan),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any], *, verify_id: bool = True) -> "GraphProposal":
        proposal = cls.create(
            str(value["run_id"]),
            str(value["base_version"]),
            tuple(value.get("read_set", ())),
            tuple(value.get("write_set", ())),
            tuple(GraphOperation.from_dict(item) for item in value.get("operations", ())),
            tuple(value.get("premise_event_ids", ())),
            tuple(value.get("validation_plan", ())),
        )
        if verify_id and value.get("proposal_id") != proposal.proposal_id:
            raise ValueError("proposal_id does not match canonical proposal content")
        return proposal
