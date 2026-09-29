"""Content-addressed recovery-point manifests for staged CAD runs."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from gencore.events import canonical_hash


@dataclass(frozen=True)
class RecoveryPoint:
    recovery_id: str
    run_id: str
    graph_version: str
    model_version: str
    artifact_refs: tuple[Mapping[str, Any], ...]

    @classmethod
    def create(
        cls,
        *,
        run_id: str,
        graph_version: str,
        model_version: str,
        artifact_refs: Sequence[Mapping[str, Any]],
    ) -> "RecoveryPoint":
        refs = tuple(
            MappingProxyType(dict(item))
            for item in sorted(
                artifact_refs,
                key=lambda item: (
                    str(item.get("artifact_id", "")),
                    str(item.get("locator", "")),
                ),
            )
        )
        body = {
            "run_id": run_id,
            "graph_version": graph_version,
            "model_version": model_version,
            "artifact_refs": [dict(item) for item in refs],
        }
        return cls(
            recovery_id="recovery:" + canonical_hash(body),
            run_id=run_id,
            graph_version=graph_version,
            model_version=model_version,
            artifact_refs=refs,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "recovery_id": self.recovery_id,
            "run_id": self.run_id,
            "graph_version": self.graph_version,
            "model_version": self.model_version,
            "artifact_refs": [dict(item) for item in self.artifact_refs],
        }


__all__ = ["RecoveryPoint"]
