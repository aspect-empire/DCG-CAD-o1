"""Framework-neutral contracts for staged CAD execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from gencore.events import canonical_hash


class CadOperationKind(str, Enum):
    PROBE_SESSION = "probe_session"
    BUILD_COMPARTMENT_SCENE = "build_compartment_scene"
    CREATE_FOUNDATION = "create_foundation"
    UPDATE_PARAMETERS = "update_parameters"
    UPDATE_HOLES = "update_holes"
    UPDATE_GUSSETS = "update_gussets"
    ASSEMBLE_FOUNDATION = "assemble_foundation"
    UPDATE_MODEL = "update_model"
    EXPORT = "export"
    CHECK_INTERFERENCE = "check_interference"
    RELOCATE_REFERENCES = "relocate_references"
    CREATE_RECOVERY_POINT = "create_recovery_point"
    ROLLBACK = "rollback"


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


@dataclass(frozen=True)
class CadOperation:
    operation_id: str
    idempotency_key: str
    kind: CadOperationKind
    run_id: str
    graph_version: str
    model_version: str
    targets: tuple[str, ...]
    parameters: Mapping[str, Any] = field(default_factory=dict)
    options: Mapping[str, Any] = field(default_factory=dict)
    required_validations: tuple[str, ...] = ()

    @classmethod
    def create(
        cls,
        kind: CadOperationKind | str,
        *,
        run_id: str,
        graph_version: str,
        model_version: str,
        targets: Sequence[str],
        parameters: Mapping[str, Any] | None = None,
        options: Mapping[str, Any] | None = None,
        required_validations: Sequence[str] = (),
    ) -> "CadOperation":
        operation_kind = CadOperationKind(kind)
        if not run_id or not graph_version or not model_version:
            raise ValueError("run_id, graph_version and model_version are required")
        target_tuple = tuple(sorted({str(item) for item in targets}))
        if operation_kind is not CadOperationKind.PROBE_SESSION and not target_tuple:
            raise ValueError("CAD write and validation operations require targets")
        body = {
            "kind": operation_kind.value,
            "run_id": str(run_id),
            "graph_version": str(graph_version),
            "model_version": str(model_version),
            "targets": list(target_tuple),
            "parameters": dict(parameters or {}),
            "options": dict(options or {}),
            "required_validations": list(
                dict.fromkeys(str(item) for item in required_validations)
            ),
        }
        digest = canonical_hash(body)
        return cls(
            operation_id="cadop:" + digest,
            idempotency_key="idem:" + digest,
            kind=operation_kind,
            run_id=str(run_id),
            graph_version=str(graph_version),
            model_version=str(model_version),
            targets=target_tuple,
            parameters=_freeze(body["parameters"]),
            options=_freeze(body["options"]),
            required_validations=tuple(body["required_validations"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "idempotency_key": self.idempotency_key,
            "kind": self.kind.value,
            "run_id": self.run_id,
            "graph_version": self.graph_version,
            "model_version": self.model_version,
            "targets": list(self.targets),
            "parameters": _thaw(self.parameters),
            "options": _thaw(self.options),
            "required_validations": list(self.required_validations),
        }


@dataclass(frozen=True)
class CadOperationResult:
    result_id: str
    operation_id: str
    idempotency_key: str
    status: str
    backend: str
    run_id: str
    graph_version: str
    model_version: str
    affected_objects: tuple[str, ...] = ()
    failure_class: str | None = None
    logs: tuple[str, ...] = ()
    geometry_reference_changes: tuple[Mapping[str, Any], ...] = ()
    artifact_refs: tuple[Mapping[str, Any], ...] = ()
    required_validations: tuple[str, ...] = ()

    @classmethod
    def from_operation(
        cls,
        operation: CadOperation,
        *,
        status: str,
        backend: str,
        affected_objects: Sequence[str] = (),
        failure_class: str | None = None,
        logs: Sequence[str] = (),
        geometry_reference_changes: Sequence[Mapping[str, Any]] = (),
        artifact_refs: Sequence[Mapping[str, Any]] = (),
        required_validations: Sequence[str] | None = None,
    ) -> "CadOperationResult":
        if not status or not backend:
            raise ValueError("CAD result status and backend are required")
        body = {
            "operation_id": operation.operation_id,
            "idempotency_key": operation.idempotency_key,
            "status": str(status),
            "backend": str(backend),
            "run_id": operation.run_id,
            "graph_version": operation.graph_version,
            "model_version": operation.model_version,
            "affected_objects": [str(item) for item in affected_objects],
            "failure_class": failure_class,
            "logs": [str(item) for item in logs],
            "geometry_reference_changes": [
                dict(item) for item in geometry_reference_changes
            ],
            "artifact_refs": [dict(item) for item in artifact_refs],
            "required_validations": list(
                operation.required_validations
                if required_validations is None
                else required_validations
            ),
        }
        return cls(
            result_id="cadresult:" + canonical_hash(body),
            operation_id=operation.operation_id,
            idempotency_key=operation.idempotency_key,
            status=body["status"],
            backend=body["backend"],
            run_id=operation.run_id,
            graph_version=operation.graph_version,
            model_version=operation.model_version,
            affected_objects=tuple(body["affected_objects"]),
            failure_class=failure_class,
            logs=tuple(body["logs"]),
            geometry_reference_changes=tuple(
                _freeze(item) for item in body["geometry_reference_changes"]
            ),
            artifact_refs=tuple(_freeze(item) for item in body["artifact_refs"]),
            required_validations=tuple(body["required_validations"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "result_id": self.result_id,
            "operation_id": self.operation_id,
            "idempotency_key": self.idempotency_key,
            "status": self.status,
            "backend": self.backend,
            "run_id": self.run_id,
            "graph_version": self.graph_version,
            "model_version": self.model_version,
            "affected_objects": list(self.affected_objects),
            "failure_class": self.failure_class,
            "logs": list(self.logs),
            "geometry_reference_changes": _thaw(self.geometry_reference_changes),
            "artifact_refs": _thaw(self.artifact_refs),
            "required_validations": list(self.required_validations),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CadOperationResult":
        result = cls(
            result_id=str(value["result_id"]),
            operation_id=str(value["operation_id"]),
            idempotency_key=str(value["idempotency_key"]),
            status=str(value["status"]),
            backend=str(value["backend"]),
            run_id=str(value["run_id"]),
            graph_version=str(value["graph_version"]),
            model_version=str(value["model_version"]),
            affected_objects=tuple(str(item) for item in value.get("affected_objects", ())),
            failure_class=(
                str(value["failure_class"])
                if value.get("failure_class") is not None
                else None
            ),
            logs=tuple(str(item) for item in value.get("logs", ())),
            geometry_reference_changes=tuple(
                _freeze(item)
                for item in value.get("geometry_reference_changes", ())
            ),
            artifact_refs=tuple(
                _freeze(item) for item in value.get("artifact_refs", ())
            ),
            required_validations=tuple(
                str(item) for item in value.get("required_validations", ())
            ),
        )
        body = result.to_dict()
        supplied = body.pop("result_id")
        if supplied != "cadresult:" + canonical_hash(body):
            raise ValueError("CAD result_id does not match canonical content")
        return result


__all__ = ["CadOperation", "CadOperationKind", "CadOperationResult"]
