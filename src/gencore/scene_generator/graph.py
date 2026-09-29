from __future__ import annotations

from typing import Any

from .core import SceneObject


def export_graph(objects: list[SceneObject], expected_interferences: list[dict[str, Any]]) -> dict[str, Any]:
    nodes = [obj.to_graph_node() for obj in objects if not obj.type.endswith("Segment")]
    edges: list[dict[str, str]] = []
    ids_by_type: dict[str, list[str]] = {}
    for obj in objects:
        ids_by_type.setdefault(obj.type, []).append(obj.id)

    deck_id = ids_by_type.get("Deck", ["DECK_001"])[0]
    for obj in objects:
        if obj.type in {"DeckLongitudinal", "DeckTransverse", "Bulkhead"}:
            edges.append({"source": obj.id, "target": deck_id, "relation": "mounted_on"})
        if obj.type == "BulkheadStiffener":
            edges.append({"source": obj.id, "target": obj.properties.get("bulkhead_id", ""), "relation": "has_stiffener"})
        if obj.type == "Equipment":
            edges.append({"source": obj.id, "target": deck_id, "relation": "located_on"})
        if obj.type == "MountingFace":
            edges.append({"source": obj.properties["equipment_id"], "target": obj.id, "relation": "has_mounting_face"})
        if obj.type == "MountingHole":
            edges.append({"source": obj.properties["equipment_id"], "target": obj.id, "relation": "has_mounting_hole"})
        if obj.type == "FoundationDesignZone":
            related = obj.properties.get("related_equipment", "EQ_001")
            edges.append({"source": related, "target": obj.id, "relation": "requires_foundation"})

    for conflict in expected_interferences:
        source = conflict.get("object_id")
        target = conflict.get("target_zone")
        if source and target:
            relation = "passes_through_zone" if "pipe" in conflict.get("type", "") else "near_zone"
            edges.append({"source": source, "target": target, "relation": relation})
            edges.append({"source": source, "target": target, "relation": "expected_conflict_with"})
    return {"nodes": nodes, "edges": edges}
