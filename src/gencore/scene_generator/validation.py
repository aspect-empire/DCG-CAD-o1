from __future__ import annotations

from typing import Any

from .core import SceneBundle, zone_bbox


def validate_scene(config: dict[str, Any], bundle: SceneBundle) -> dict[str, Any]:
    warnings: list[str] = []
    errors: list[str] = []
    objects = {obj.id: obj for obj in bundle.objects}
    deck = objects.get("DECK_001")

    for obj in bundle.objects:
        if deck and obj.type in {"Equipment", "DeckLongitudinal", "DeckTransverse"} and not deck.bbox.contains_xy(obj.bbox):
            errors.append(f"{obj.id} exceeds deck XY boundary.")

    for interface in bundle.equipment_interfaces:
        face_size = interface["mounting_face"]["size"]
        half_x, half_y = face_size[0] / 2, face_size[1] / 2
        center = interface["mounting_face"]["center"]
        for hole in interface["mounting_holes"]:
            x, y, _ = hole["global_position"]
            if not (center[0] - half_x <= x <= center[0] + half_x and center[1] - half_y <= y <= center[1] + half_y):
                errors.append(f"{hole['id']} is outside mounting face.")

    expected = config.get("expected_interferences", [])
    task = config.get("task_type", "T1")
    if task == "T1" and expected:
        errors.append("T1 scene must not include expected interferences.")
    if task == "T2" and not expected:
        errors.append("T2 scene must include at least one expected interference.")

    if expected and config.get("foundation_design_zone"):
        fdz = zone_bbox(config["foundation_design_zone"])
        for conflict in expected:
            obj = objects.get(conflict.get("object_id"))
            if obj and not obj.bbox.overlaps(fdz):
                errors.append(f"{obj.id} does not overlap {conflict.get('target_zone')}.")

    counts = {
        "deck": sum(1 for obj in bundle.objects if obj.type == "Deck"),
        "longitudinals": sum(1 for obj in bundle.objects if obj.type == "DeckLongitudinal"),
        "transverses": sum(1 for obj in bundle.objects if obj.type == "DeckTransverse"),
        "bulkheads": sum(1 for obj in bundle.objects if obj.type == "Bulkhead"),
        "pipes": len(config.get("pipes", [])),
        "cables": len(config.get("cables", [])),
        "equipments": len(config.get("equipment", [])),
    }
    return {"case_id": config.get("scene_id"), "valid": not errors, "errors": errors, "warnings": warnings, "expected_interference_count": len(expected), "object_count": counts}
