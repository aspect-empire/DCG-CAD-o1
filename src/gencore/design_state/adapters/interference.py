"""Interference reports to validation, G5 spatial and local invalidation records."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..dependencies import affected_closure
from ..ontology import View
from ..proposals import GraphOperation, GraphProposal
from ..records import DesignNode, EvidenceRef
from .common import edge_operation, proposal_from_operations


class InterferenceAdapter:
    def adapt(self, payload: Mapping[str, Any], *, base_version: str) -> GraphProposal:
        evidence = EvidenceRef(
            str(payload["artifact_id"]),
            "application/json",
            "$",
            str(payload["sha256"]),
        )
        validation = DesignNode.create(
            View.RESULT_EVIDENCE,
            "Validation",
            str(payload["report_id"]),
            {"status": payload["status"], "report_id": payload["report_id"]},
            (evidence,),
        )
        operations: list[GraphOperation] = [GraphOperation("add_node", validation.uid, validation.to_dict())]
        for index, clash in enumerate(payload.get("clashes", ())):
            clash_evidence = EvidenceRef(
                str(payload["artifact_id"]),
                "application/json",
                f"$.clashes[{index}]",
                str(payload["sha256"]),
            )
            spatial = DesignNode.create(
                View.GEOMETRY_SPATIAL,
                "DerivedSpatialObject",
                str(clash["clash_id"]),
                {"geometry_level": "G5", "spatial_type": "interference", **dict(clash)},
                (clash_evidence,),
            )
            operations.append(GraphOperation("add_node", spatial.uid, spatial.to_dict()))
            operations.append(edge_operation(validation.uid, spatial.uid, "VALIDATES"))

        dependencies = {key: set(value) for key, value in payload.get("dependencies", {}).items()}
        affected = affected_closure(dependencies, set(payload.get("changed_uids", ())))
        premises = tuple(sorted(set(payload.get("premise_event_ids", ()))))
        passed = payload.get("status") == "passed"
        for uid in sorted(affected):
            operations.append(
                GraphOperation(
                    "set_node_state",
                    uid,
                    {
                        "state": "verified" if passed else "conflicted",
                        "invalidated_by": list(premises),
                        "state_reason": "interference_passed" if passed else "interference_failed",
                    },
                )
            )
        return proposal_from_operations(
            run_id=str(payload["run_id"]),
            base_version=base_version,
            operations=operations,
            premise_event_ids=premises,
            read_set=tuple(sorted(affected)),
        )
