"""Guarded dispatch from portable CAD operations to an optional CATIA backend."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping

from .contracts import CadOperation, CadOperationKind, CadOperationResult
from .idempotency import IdempotencyLedger


_DISPATCH = {
    CadOperationKind.PROBE_SESSION: "probe_session",
    CadOperationKind.BUILD_COMPARTMENT_SCENE: "build_compartment_scene",
    CadOperationKind.CREATE_FOUNDATION: "create_foundation",
    CadOperationKind.UPDATE_PARAMETERS: "apply_parametric_model_update",
    CadOperationKind.UPDATE_HOLES: "update_holes",
    CadOperationKind.UPDATE_GUSSETS: "update_gussets",
    CadOperationKind.ASSEMBLE_FOUNDATION: "assemble_foundation",
    CadOperationKind.UPDATE_MODEL: "update_model",
    CadOperationKind.EXPORT: "export_model",
    CadOperationKind.CHECK_INTERFERENCE: "check_interference",
    CadOperationKind.RELOCATE_REFERENCES: "relocate_references",
    CadOperationKind.CREATE_RECOVERY_POINT: "create_recovery_point",
    CadOperationKind.ROLLBACK: "rollback",
}
_READ_ONLY_KINDS = {
    CadOperationKind.PROBE_SESSION,
    CadOperationKind.CHECK_INTERFERENCE,
}


class CadOperationService:
    """Execute typed CAD operations with approval and idempotency controls."""

    def __init__(self, backend: Any, *, workspace_root: str | Path) -> None:
        self.backend = backend
        self.workspace_root = Path(workspace_root)

    def execute(
        self, operation: CadOperation, *, approved: bool
    ) -> CadOperationResult:
        if operation.kind not in _READ_ONLY_KINDS and not approved:
            return CadOperationResult.from_operation(
                operation,
                status="approval_required",
                backend=self._backend_name(),
                failure_class="approval_required",
                logs=("external CAD write requires explicit approval",),
            )

        ledger = IdempotencyLedger(self.workspace_root, run_id=operation.run_id)
        existing = ledger.lookup(operation.idempotency_key)
        if existing is not None:
            return CadOperationResult.from_dict(existing["result"])

        try:
            method = getattr(self.backend, _DISPATCH[operation.kind])
            raw = method(self._payload(operation))
            if not isinstance(raw, Mapping):
                raise TypeError("CAD backend returned a non-mapping result")
            result = self._normalize(operation, raw)
        except Exception as exc:  # external boundary must never leak exceptions
            result = CadOperationResult.from_operation(
                operation,
                status="failed",
                backend=self._backend_name(),
                failure_class=type(exc).__name__,
                logs=(str(exc),),
            )
        ledger.record(operation.idempotency_key, {"result": result.to_dict()})
        return result

    def _backend_name(self) -> str:
        return str(getattr(self.backend, "name", "CATIA"))

    @staticmethod
    def _payload(operation: CadOperation) -> dict[str, Any]:
        serialized = operation.to_dict()
        return {
            "task_id": operation.operation_id.removeprefix("cadop:")[:16],
            "run_id": operation.run_id,
            "graph_version": operation.graph_version,
            "model_version": operation.model_version,
            "targets": list(operation.targets),
            "parameters": serialized["parameters"],
            **serialized["options"],
        }

    def _normalize(
        self, operation: CadOperation, raw: Mapping[str, Any]
    ) -> CadOperationResult:
        success = raw.get("success")
        status = str(raw.get("status") or ("completed" if success is True else "failed"))
        failure_class = None
        if status not in {"completed", "success", "passed"}:
            status = "failed"
            failure_class = str(raw.get("failure_class") or "backend_failure")
        artifacts = self._artifact_refs(raw)
        errors = raw.get("errors", ())
        if isinstance(errors, str):
            errors = (errors,)
        logs = tuple(str(item) for item in raw.get("logs", ())) + tuple(
            str(item) for item in errors
        )
        affected = raw.get("affected_objects", operation.targets)
        geometry_changes = raw.get("geometry_reference_changes", ())
        return CadOperationResult.from_operation(
            operation,
            status="completed" if status in {"completed", "success", "passed"} else status,
            backend=str(raw.get("backend") or self._backend_name()),
            affected_objects=tuple(str(item) for item in affected),
            failure_class=failure_class,
            logs=logs,
            geometry_reference_changes=tuple(geometry_changes),
            artifact_refs=artifacts,
        )

    @staticmethod
    def _artifact_refs(raw: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
        supplied = raw.get("artifact_refs") or raw.get("artifacts")
        if supplied:
            return tuple(dict(item) for item in supplied)
        exported = raw.get("exported_files", {})
        refs: list[dict[str, Any]] = []
        if isinstance(exported, Mapping):
            for format_name, value in sorted(exported.items()):
                path = Path(str(value))
                if path.is_file():
                    refs.append(
                        {
                            "artifact_id": f"cad-export:{format_name.lower()}",
                            "locator": str(path),
                            "media_type": f"model/{format_name.lower()}",
                            "sha256": sha256(path.read_bytes()).hexdigest(),
                        }
                    )
        return tuple(refs)


class OptionalCatiaBackend:
    """Small CATIA boundary retained by the public method package.

    The public release implements session probing and compartment-scene
    generation. Foundation-model construction and organization-specific update
    scripts remain outside this release and therefore fail explicitly.
    """

    name = "CATIA"

    def probe_session(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        from pycatia import catia

        app = catia()
        application = getattr(app, "application", app)
        documents = getattr(application, "documents", None)
        return {
            "status": "completed",
            "backend": self.name,
            "available": application is not None,
            "document_count": getattr(documents, "count", None),
        }

    def build_compartment_scene(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        from gencore.scene_generator.catia_api.scene_builder import build_catia_scene

        output_path = payload.get("output_path")
        config = payload.get("config") or payload.get("parameters")
        if not output_path or not isinstance(config, Mapping):
            raise ValueError("config and output_path are required")
        target = build_catia_scene(
            dict(config), output_path, visible=bool(payload.get("visible", True))
        )
        return {
            "status": "completed",
            "affected_objects": list(payload.get("targets", ())),
            "exported_files": {"CATProduct": str(target)},
        }

    @staticmethod
    def _not_in_public_release(operation: str) -> dict[str, Any]:
        raise NotImplementedError(
            f"{operation} requires the production CAD implementation, which is not included"
        )

    def create_foundation(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        return self._not_in_public_release("create_foundation")

    def apply_parametric_model_update(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        return self._not_in_public_release("update_parameters")

    def update_holes(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        return self._not_in_public_release("update_holes")

    def update_gussets(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        return self._not_in_public_release("update_gussets")

    def assemble_foundation(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        return self._not_in_public_release("assemble_foundation")

    def update_model(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        return self._not_in_public_release("update_model")

    def export_model(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        return self._not_in_public_release("export")

    def check_interference(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        return self._not_in_public_release("check_interference")

    def relocate_references(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        return self._not_in_public_release("relocate_references")

    def create_recovery_point(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "status": "completed",
            "affected_objects": list(payload.get("targets", ())),
            "artifacts": list(payload.get("artifact_refs", ())),
        }

    def rollback(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        return self._not_in_public_release("rollback")


# Backward-compatible name retained for existing method integrations.
MigratedCadBackend = OptionalCatiaBackend


__all__ = ["CadOperationService", "MigratedCadBackend", "OptionalCatiaBackend"]
