"""Route typed tool evidence through existing graph adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from gencore.design_state import GraphProposal
from gencore.design_state.adapters.catia_pipeline import CatiaPipelineAdapter
from gencore.design_state.adapters.interference import InterferenceAdapter
from gencore.design_state.adapters.scene import SceneAdapter
from gencore.events import canonical_hash
from gencore.ports.tool_executor import ToolOutcome, ToolRequest

from .roles import AgentRole


@dataclass(frozen=True)
class RoutedProposal:
    role: AgentRole
    proposal: GraphProposal


class EvidenceRouter:
    @classmethod
    def default(cls) -> "EvidenceRouter":
        return cls()

    def to_proposal(
        self,
        *,
        request: ToolRequest,
        outcome: ToolOutcome,
        base_version: str,
    ) -> RoutedProposal:
        result = dict(outcome.result)
        if isinstance(result.get("graph_proposal"), Mapping):
            role = self._role_for(request.name)
            original = GraphProposal.from_dict(result["graph_proposal"])
            premise_event_ids = tuple(
                sorted(
                    {
                        *original.premise_event_ids,
                        *(
                            (outcome.approval_event_id,)
                            if outcome.approval_event_id
                            else ()
                        ),
                    }
                )
            )
            proposal = (
                original
                if original.base_version == base_version
                and premise_event_ids == original.premise_event_ids
                else GraphProposal.create(
                    original.run_id,
                    base_version,
                    original.read_set,
                    original.write_set,
                    original.operations,
                    premise_event_ids,
                    original.validation_plan,
                )
            )
            return RoutedProposal(role, proposal)

        if request.name.startswith("geometry.scene."):
            payload = dict(result.get("scene_payload") or result)
            payload.setdefault("run_id", str(request.payload.get("run_id", "scene")))
            return RoutedProposal(
                AgentRole.SCENE_CONSTRAINT,
                SceneAdapter().adapt(payload, base_version=base_version),
            )

        if request.name == "geometry.cad.check_interference" and isinstance(
            result.get("interference_report"), Mapping
        ):
            return RoutedProposal(
                AgentRole.VALIDATION,
                InterferenceAdapter().adapt(
                    result["interference_report"], base_version=base_version
                ),
            )

        if request.name.startswith("geometry.cad."):
            manifest = dict(result.get("catia_manifest") or {})
            if not manifest:
                digest = canonical_hash(result)
                manifest = {
                    "run_id": str(
                        result.get("run_id")
                        or request.payload.get("run_id")
                        or "cad-run"
                    ),
                    "execution_id": str(
                        result.get("operation_id")
                        or request.operation_id
                        or f"execution:{digest}"
                    ),
                    "stage": request.name,
                    "status": (
                        "completed"
                        if outcome.status == "completed"
                        and result.get("status") in {"completed", "passed", "success"}
                        else "failed"
                    ),
                    "artifact_id": f"artifact:cad-manifest:{digest}",
                    "sha256": digest,
                    "artifacts": [
                        {
                            "artifact_id": str(
                                item.get("artifact_id", f"artifact:{index}")
                            ),
                            "path": str(item.get("locator", "")),
                            **dict(item),
                        }
                        for index, item in enumerate(result.get("artifact_refs", ()), 1)
                    ],
                    "failure": {
                        "code": str(result.get("failure_class") or "CAD_FAILED"),
                        "message": "; ".join(map(str, result.get("logs", ()))),
                    },
                }
            if outcome.approval_event_id:
                manifest["approval_event_id"] = outcome.approval_event_id
                manifest["premise_event_ids"] = sorted(
                    {
                        *manifest.get("premise_event_ids", ()),
                        outcome.approval_event_id,
                    }
                )
            role = (
                AgentRole.VALIDATION
                if request.name == "geometry.cad.check_interference"
                else AgentRole.CAD_EXECUTOR
            )
            return RoutedProposal(
                role,
                CatiaPipelineAdapter().adapt(manifest, base_version=base_version),
            )

        raise ValueError(f"unsupported evidence route: {request.name}")

    @staticmethod
    def _role_for(tool_name: str) -> AgentRole:
        if tool_name.startswith("foundation.case_matching.") or tool_name.startswith(
            "foundation.parameters."
        ):
            return AgentRole.SOLUTION_PARAMETER
        if tool_name.startswith("geometry.scene."):
            return AgentRole.SCENE_CONSTRAINT
        if tool_name.startswith("geometry.cad."):
            return (
                AgentRole.VALIDATION
                if tool_name == "geometry.cad.check_interference"
                else AgentRole.CAD_EXECUTOR
            )
        raise ValueError(f"unsupported evidence route: {tool_name}")


__all__ = ["EvidenceRouter", "RoutedProposal"]
