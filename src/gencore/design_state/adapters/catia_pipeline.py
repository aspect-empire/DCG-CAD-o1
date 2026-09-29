"""CATIA pipeline manifests to process, geometry and evidence graph records."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..ontology import View
from ..proposals import GraphOperation, GraphProposal
from ..records import DesignNode, EvidenceRef
from .common import edge_operation, proposal_from_operations


class CatiaPipelineAdapter:
    COLLECTIONS = (
        ("artifacts", View.RESULT_EVIDENCE, "Artifact", "artifact_id"),
        ("features", View.GEOMETRY_SPATIAL, "ModelFeature", "feature_id"),
        ("boundaries", View.GEOMETRY_SPATIAL, "GeometryBoundary", "reference_id"),
        ("keypoints", View.GEOMETRY_SPATIAL, "GeometryKeypoint", "reference_id"),
        ("derived_spatial", View.GEOMETRY_SPATIAL, "DerivedSpatialObject", "reference_id"),
    )

    def adapt(self, manifest: Mapping[str, Any], *, base_version: str) -> GraphProposal:
        evidence = EvidenceRef(
            str(manifest["artifact_id"]),
            "application/json",
            "$",
            str(manifest["sha256"]),
        )
        execution = DesignNode.create(
            View.PROCESS_TOOL,
            "Execution",
            str(manifest["execution_id"]),
            {
                "execution_id": manifest["execution_id"],
                "stage": manifest["stage"],
                "status": manifest.get("status", "failed"),
                "environment": manifest.get("environment", {}),
                "approval_event_id": manifest.get("approval_event_id"),
            },
            (evidence,),
        )
        operations: list[GraphOperation] = [GraphOperation("add_node", execution.uid, execution.to_dict())]
        for collection, view, node_type, key in self.COLLECTIONS:
            for index, item in enumerate(manifest.get(collection, ())):
                item_evidence = EvidenceRef(
                    str(manifest["artifact_id"]),
                    "application/json",
                    f"$.{collection}[{index}]",
                    str(manifest["sha256"]),
                )
                node = DesignNode.create(view, node_type, str(item[key]), dict(item), (item_evidence,))
                operations.append(GraphOperation("add_node", node.uid, node.to_dict()))
                operations.append(edge_operation(execution.uid, node.uid, "PRODUCES"))
        if manifest.get("status") != "completed":
            failure = dict(manifest.get("failure") or {"code": "CATIA_FAILED", "message": "CATIA stage did not complete"})
            failure_node = DesignNode.create(
                View.RESULT_EVIDENCE,
                "FailureSignature",
                f"{manifest['execution_id']}:{failure.get('code', 'CATIA_FAILED')}",
                {"status": "failed", **failure},
                (evidence,),
            )
            operations.append(GraphOperation("add_node", failure_node.uid, failure_node.to_dict()))
            operations.append(edge_operation(execution.uid, failure_node.uid, "TRIGGERS"))
        return proposal_from_operations(
            run_id=str(manifest["run_id"]),
            base_version=base_version,
            operations=operations,
            premise_event_ids=tuple(manifest.get("premise_event_ids", ())),
        )
