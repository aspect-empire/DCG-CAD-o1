"""Compartment scene JSON to product, geometry and artifact graph records."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from gencore.events import canonical_hash

from ..ontology import View
from ..proposals import GraphOperation, GraphProposal
from ..records import DesignNode, EvidenceRef
from .common import edge_operation, proposal_from_operations


class SceneAdapter:
    def adapt(self, payload: Mapping[str, Any], *, base_version: str) -> GraphProposal:
        digest = str(payload.get("sha256") or canonical_hash(payload))
        artifact_id = str(payload.get("artifact_id", f"artifact:{digest}"))

        def evidence(locator: str) -> tuple[EvidenceRef, ...]:
            return (EvidenceRef(artifact_id, "application/json", locator, digest),)

        operations: list[GraphOperation] = []
        cabin = DesignNode.create(
            View.PRODUCT_FUNCTION,
            "Cabin",
            str(payload["scene_id"]),
            {"name": payload["scene_id"], "compartment": payload.get("compartment", {})},
            evidence("$.compartment"),
        )
        operations.append(GraphOperation("add_node", cabin.uid, cabin.to_dict()))

        for index, equipment in enumerate(payload.get("equipment", ())):
            equipment_node = DesignNode.create(
                View.PRODUCT_FUNCTION,
                "Equipment",
                str(equipment["id"]),
                {"name": equipment["id"], "equipment_type": equipment.get("equipment_type"), "origin": equipment.get("origin")},
                evidence(f"$.equipment[{index}]"),
            )
            operations.append(GraphOperation("add_node", equipment_node.uid, equipment_node.to_dict()))
            operations.append(edge_operation(cabin.uid, equipment_node.uid, "CONTAINS"))
            mounting_face = equipment.get("mounting_face")
            if mounting_face:
                interface = DesignNode.create(
                    View.GEOMETRY_SPATIAL,
                    "Interface",
                    f"{equipment['id']}:{mounting_face['face_id']}",
                    {"semantic_role": "mounting_face", **dict(mounting_face)},
                    evidence(f"$.equipment[{index}].mounting_face"),
                )
                operations.append(GraphOperation("add_node", interface.uid, interface.to_dict()))
                operations.append(edge_operation(equipment_node.uid, interface.uid, "HAS_INTERFACE"))
            for hole_index, hole in enumerate(equipment.get("mounting_holes", ())):
                keypoint = DesignNode.create(
                    View.GEOMETRY_SPATIAL,
                    "Keypoint",
                    f"{equipment['id']}:{hole['id']}",
                    {"semantic_role": "mounting_hole_center", **dict(hole)},
                    evidence(f"$.equipment[{index}].mounting_holes[{hole_index}]"),
                )
                operations.append(GraphOperation("add_node", keypoint.uid, keypoint.to_dict()))
                operations.append(edge_operation(equipment_node.uid, keypoint.uid, "HAS_KEYPOINT"))

        artifact = payload.get("artifact")
        if artifact:
            artifact_node = DesignNode.create(
                View.RESULT_EVIDENCE,
                "Artifact",
                str(artifact.get("artifact_id") or artifact["path"]),
                dict(artifact),
                evidence("$.artifact"),
            )
            operations.append(GraphOperation("add_node", artifact_node.uid, artifact_node.to_dict()))
            operations.append(edge_operation(cabin.uid, artifact_node.uid, "REPRESENTED_BY"))

        return proposal_from_operations(
            run_id=str(payload["run_id"]),
            base_version=base_version,
            operations=operations,
            premise_event_ids=tuple(payload.get("premise_event_ids", ())),
        )
