"""Framework-neutral contracts for progressive geometry design runs."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import PurePosixPath, PureWindowsPath
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from gencore.events import canonical_hash


class Stage(str, Enum):
    S0_INITIALIZE = "S0_INITIALIZE"
    S1_ACTIVATE_CONSTRAINTS = "S1_ACTIVATE_CONSTRAINTS"
    S2_PLAN_GEOMETRY = "S2_PLAN_GEOMETRY"
    S3_EXECUTE_CAD = "S3_EXECUTE_CAD"
    S4_VALIDATE = "S4_VALIDATE"
    S5_REPAIR_OR_HANDOFF = "S5_REPAIR_OR_HANDOFF"


class DesignDecision(str, Enum):
    RUNNING = "RUNNING"
    ACCEPTED = "ACCEPTED"
    ABSTAINED = "ABSTAINED"
    REJECTED = "REJECTED"
    HUMAN_REQUIRED = "HUMAN_REQUIRED"


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    if isinstance(value, Enum):
        return value.value
    return value


def _record_tuple(values: Sequence[Mapping[str, Any]]) -> tuple[Mapping[str, Any], ...]:
    return tuple(_freeze(item) for item in values)


def _string_tuple(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(str(value) for value in values)


def _validate_artifact(ref: Mapping[str, Any]) -> None:
    locator = str(ref.get("locator", "")).replace("\\", "/")
    path = PurePosixPath(locator)
    if (
        not locator
        or path.is_absolute()
        or bool(PureWindowsPath(locator).drive)
        or ".." in path.parts
    ):
        raise ValueError("artifact locator must be a safe relative path")
    digest = str(ref.get("sha256", ""))
    if len(digest) != 64 or any(character not in "0123456789abcdefABCDEF" for character in digest):
        raise ValueError("artifact sha256 must be a 64-character hexadecimal digest")


@dataclass(frozen=True)
class DesignExecutionPackage:
    package_id: str
    schema_version: str
    task_id: str
    scenario_id: str
    run_id: str
    graph_version: str
    parent_version: str | None
    stage: Stage
    design_intent: Mapping[str, Any]
    visible_evidence: tuple[Mapping[str, Any], ...] = ()
    unknown_constraints: tuple[Mapping[str, Any], ...] = ()
    conflicts: tuple[Mapping[str, Any], ...] = ()
    candidate_templates: tuple[Mapping[str, Any], ...] = ()
    spatial_context: Mapping[str, Any] = field(default_factory=dict)
    constraints: tuple[Mapping[str, Any], ...] = ()
    parameters: tuple[Mapping[str, Any], ...] = ()
    geometry_references: tuple[Mapping[str, Any], ...] = ()
    model_plan: Mapping[str, Any] = field(default_factory=dict)
    operation_sequence: tuple[Mapping[str, Any], ...] = ()
    validation_plan: tuple[Mapping[str, Any], ...] = ()
    fallback_policy: Mapping[str, Any] = field(default_factory=dict)
    read_set: tuple[str, ...] = ()
    write_set: tuple[str, ...] = ()
    graph_proposals: tuple[Mapping[str, Any], ...] = ()
    commit_results: tuple[Mapping[str, Any], ...] = ()
    artifact_refs: tuple[Mapping[str, Any], ...] = ()
    validation_evidence: tuple[Mapping[str, Any], ...] = ()
    provenance: tuple[Mapping[str, Any], ...] = ()
    current_decision: DesignDecision = DesignDecision.RUNNING
    next_event: str | None = None

    @classmethod
    def create(cls, **values: Any) -> "DesignExecutionPackage":
        required = ("task_id", "scenario_id", "run_id", "graph_version", "stage", "design_intent")
        missing = [name for name in required if name not in values]
        if missing:
            raise ValueError("missing execution package fields: " + ", ".join(missing))
        for name in ("task_id", "scenario_id", "run_id", "graph_version"):
            if not isinstance(values[name], str) or not values[name]:
                raise ValueError(f"{name} must be a non-empty string")

        artifact_refs = tuple(values.get("artifact_refs", ()))
        for ref in artifact_refs:
            _validate_artifact(ref)

        body: dict[str, Any] = {
            "schema_version": str(values.get("schema_version", "1.0")),
            "task_id": values["task_id"],
            "scenario_id": values["scenario_id"],
            "run_id": values["run_id"],
            "graph_version": values["graph_version"],
            "parent_version": values.get("parent_version"),
            "stage": Stage(values["stage"]),
            "design_intent": _freeze(values["design_intent"]),
            "spatial_context": _freeze(values.get("spatial_context", {})),
            "model_plan": _freeze(values.get("model_plan", {})),
            "fallback_policy": _freeze(values.get("fallback_policy", {})),
            "read_set": _string_tuple(values.get("read_set", ())),
            "write_set": _string_tuple(values.get("write_set", ())),
            "current_decision": DesignDecision(
                values.get("current_decision", DesignDecision.RUNNING)
            ),
            "next_event": values.get("next_event"),
        }
        for name in (
            "visible_evidence",
            "unknown_constraints",
            "conflicts",
            "candidate_templates",
            "constraints",
            "parameters",
            "geometry_references",
            "operation_sequence",
            "validation_plan",
            "graph_proposals",
            "commit_results",
            "validation_evidence",
            "provenance",
        ):
            body[name] = _record_tuple(values.get(name, ()))
        body["artifact_refs"] = _record_tuple(artifact_refs)
        identity = _thaw(body)
        return cls(package_id="dep:" + canonical_hash(identity), **body)

    def to_dict(self) -> dict[str, Any]:
        return {
            "package_id": self.package_id,
            "schema_version": self.schema_version,
            "task_id": self.task_id,
            "scenario_id": self.scenario_id,
            "run_id": self.run_id,
            "graph_version": self.graph_version,
            "parent_version": self.parent_version,
            "stage": self.stage.value,
            "design_intent": _thaw(self.design_intent),
            "visible_evidence": _thaw(self.visible_evidence),
            "unknown_constraints": _thaw(self.unknown_constraints),
            "conflicts": _thaw(self.conflicts),
            "candidate_templates": _thaw(self.candidate_templates),
            "spatial_context": _thaw(self.spatial_context),
            "constraints": _thaw(self.constraints),
            "parameters": _thaw(self.parameters),
            "geometry_references": _thaw(self.geometry_references),
            "model_plan": _thaw(self.model_plan),
            "operation_sequence": _thaw(self.operation_sequence),
            "validation_plan": _thaw(self.validation_plan),
            "fallback_policy": _thaw(self.fallback_policy),
            "read_set": list(self.read_set),
            "write_set": list(self.write_set),
            "graph_proposals": _thaw(self.graph_proposals),
            "commit_results": _thaw(self.commit_results),
            "artifact_refs": _thaw(self.artifact_refs),
            "validation_evidence": _thaw(self.validation_evidence),
            "provenance": _thaw(self.provenance),
            "current_decision": self.current_decision.value,
            "next_event": self.next_event,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "DesignExecutionPackage":
        supplied = dict(value)
        package_id = str(supplied.pop("package_id", ""))
        restored = cls.create(**supplied)
        if restored.package_id != package_id:
            raise ValueError("package_id does not match canonical content")
        return restored


@dataclass(frozen=True)
class AgentOutcome:
    status: str
    graph_proposals: tuple[Mapping[str, Any], ...] = ()
    tool_requests: tuple[Mapping[str, Any], ...] = ()
    missing_inputs: tuple[str, ...] = ()
    risks: tuple[str, ...] = ()
    blocker_ids: tuple[str, ...] = ()
    suggested_tasks: tuple[Mapping[str, Any], ...] = ()
    evidence_refs: tuple[str, ...] = ()
    requested_decision: DesignDecision = DesignDecision.RUNNING

    def __post_init__(self) -> None:
        if not self.status:
            raise ValueError("AgentOutcome status must be non-empty")
        if self.requested_decision is DesignDecision.ACCEPTED:
            raise ValueError("only DecisionEvaluator may produce ACCEPTED")
        object.__setattr__(self, "graph_proposals", _record_tuple(self.graph_proposals))
        object.__setattr__(self, "tool_requests", _record_tuple(self.tool_requests))
        object.__setattr__(self, "suggested_tasks", _record_tuple(self.suggested_tasks))
        object.__setattr__(self, "missing_inputs", _string_tuple(self.missing_inputs))
        object.__setattr__(self, "risks", _string_tuple(self.risks))
        object.__setattr__(self, "blocker_ids", _string_tuple(self.blocker_ids))
        object.__setattr__(self, "evidence_refs", _string_tuple(self.evidence_refs))


__all__ = [
    "AgentOutcome",
    "DesignDecision",
    "DesignExecutionPackage",
    "Stage",
]
