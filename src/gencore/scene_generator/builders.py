from __future__ import annotations

from typing import Any

from .core import BBox, SceneObject, point3, segment_bbox, zone_bbox
from .defaults import COLORS


def build_compartment(config: dict[str, Any]) -> list[SceneObject]:
    deck = config["deck"]
    origin = point3(deck.get("origin", [0, 0, 0]))
    length = float(deck["length_x"])
    width = float(deck["width_y"])
    thickness = float(deck.get("thickness", 20))
    objects = [
        SceneObject(
            id=deck.get("id", "DECK_001"),
            type="Deck",
            bbox=BBox((origin[0], origin[1], origin[2] - thickness), (origin[0] + length, origin[1] + width, origin[2])),
            properties={"length_x": length, "width_y": width, "thickness": thickness, "shape_type": deck.get("shape_type", "rectangular")},
            color=COLORS["deck_wall"],
        )
    ]

    for idx, y in enumerate(config.get("deck_longitudinals", {}).get("y_positions", []), start=1):
        spec = config["deck_longitudinals"]
        h = float(spec.get("height", 160))
        t = float(spec.get("thickness", 12))
        obj_id = f"DLG_{idx:03d}"
        objects.append(SceneObject(obj_id, "DeckLongitudinal", BBox((0, y - t / 2, -h), (length, y + t / 2, 0)), {"direction": "x", "height": h, "thickness": t}, COLORS["stiffener_beam"]))

    for idx, x in enumerate(config.get("deck_transverses", {}).get("x_positions", []), start=1):
        spec = config["deck_transverses"]
        h = float(spec.get("height", 180))
        t = float(spec.get("thickness", 14))
        obj_id = f"DTB_{idx:03d}"
        objects.append(SceneObject(obj_id, "DeckTransverse", BBox((x - t / 2, 0, -h), (x + t / 2, width, 0)), {"direction": "y", "height": h, "thickness": t}, COLORS["stiffener_beam"]))

    bulkheads_by_id: dict[str, SceneObject] = {}
    for idx, wall in enumerate(config.get("bulkheads", []), start=1):
        obj_id = wall.get("id", f"BH_{idx:03d}")
        h = float(wall.get("height", 1600))
        t = float(wall.get("thickness", 20))
        pos = float(wall["position"])
        axis_mode = _resolve_bulkhead_axis_mode(wall, length, width)
        if axis_mode == "normal_x":
            bbox = BBox((origin[0] + pos - t / 2, origin[1], 0), (origin[0] + pos + t / 2, origin[1] + width, h))
        elif axis_mode == "normal_y":
            bbox = BBox((origin[0], origin[1] + pos - t / 2, 0), (origin[0] + length, origin[1] + pos + t / 2, h))
        elif wall.get("orientation", "x") == "x":
            bbox = BBox((origin[0], origin[1] + pos - t / 2, 0), (origin[0] + length, origin[1] + pos + t / 2, h))
        else:
            bbox = BBox((origin[0] + pos - t / 2, origin[1], 0), (origin[0] + pos + t / 2, origin[1] + width, h))
        obj = SceneObject(obj_id, "Bulkhead", bbox, {"orientation": wall.get("orientation", "x"), "axis_mode": axis_mode, "height": h, "thickness": t}, COLORS["deck_wall"])
        objects.append(obj)
        bulkheads_by_id[obj_id] = obj

    stiffener_index = 1
    for spec in config.get("bulkhead_stiffeners", []):
        wall = bulkheads_by_id.get(spec["bulkhead_id"])
        if not wall:
            continue
        h = float(spec.get("height", wall.properties["height"]))
        w = float(spec.get("width", 80))
        t = float(spec.get("thickness", 12))
        for pos in spec.get("positions", []):
            if wall.properties.get("axis_mode") == "normal_x":
                x_face = wall.bbox.max[0] if wall.bbox.min[0] <= origin[0] else wall.bbox.min[0]
                if wall.bbox.min[0] <= origin[0]:
                    bbox = BBox((x_face, pos - w / 2, 0), (x_face + t, pos + w / 2, h))
                else:
                    bbox = BBox((x_face - t, pos - w / 2, 0), (x_face, pos + w / 2, h))
            elif wall.properties.get("axis_mode") == "normal_y":
                y_face = wall.bbox.max[1] if wall.bbox.min[1] <= origin[1] else wall.bbox.min[1]
                if wall.bbox.min[1] <= origin[1]:
                    bbox = BBox((pos - w / 2, y_face, 0), (pos + w / 2, y_face + t, h))
                else:
                    bbox = BBox((pos - w / 2, y_face - t, 0), (pos + w / 2, y_face, h))
            elif wall.properties["orientation"] == "x":
                y_face = wall.bbox.min[1]
                bbox = BBox((pos - w / 2, y_face - t, 0), (pos + w / 2, y_face, h))
            else:
                x_face = wall.bbox.min[0]
                bbox = BBox((x_face - t, pos - w / 2, 0), (x_face, pos + w / 2, h))
            objects.append(SceneObject(f"BHS_{stiffener_index:03d}", "BulkheadStiffener", bbox, {"bulkhead_id": wall.id, "height": h, "width": w, "thickness": t}, COLORS["stiffener_beam"]))
            stiffener_index += 1
    return objects


def _resolve_bulkhead_axis_mode(wall: dict[str, Any], length: float, width: float) -> str:
    wall_id = str(wall.get("id", "")).upper()
    orientation = wall.get("orientation", "x")
    pos = float(wall["position"])
    if wall_id.endswith("_AFT") or wall_id.endswith("_FWD") or wall_id in {"BH_AFT", "BH_FWD"}:
        return "normal_x"
    if wall_id.endswith("_PORT") or wall_id.endswith("_STBD") or wall_id in {"BH_PORT", "BH_STBD"}:
        return "normal_y"
    if orientation == "x" and pos > width and pos <= length:
        return "normal_x"
    if orientation == "y" and pos > length and pos <= width:
        return "normal_y"
    return "legacy"


def build_pipelines(pipes: list[dict[str, Any]], cables: list[dict[str, Any]]) -> tuple[list[SceneObject], list[dict[str, Any]]]:
    objects: list[SceneObject] = []
    centerlines: list[dict[str, Any]] = []
    for pipe in pipes:
        radius = float(pipe.get("cross_section", {}).get("diameter", 100)) / 2
        points = [point3(p) for p in pipe["route_nodes"]]
        whole = BBox.from_points(points, radius)
        objects.append(SceneObject(pipe["id"], "Pipe", whole, {"diameter": radius * 2, "clearance": pipe.get("clearance", 0), "movable": pipe.get("movable", False)}, COLORS["pipe"]))
        for idx, (p1, p2) in enumerate(zip(points, points[1:]), start=1):
            objects.append(SceneObject(f"{pipe['id']}_SEG_{idx:03d}", "PipeSegment", segment_bbox(p1, p2, radius), {"parent_id": pipe["id"], "radius": radius}, COLORS["pipe"]))
        centerlines.append({"id": pipe["id"], "object_type": "pipe", "route_nodes": [list(p) for p in points], "cross_section": pipe.get("cross_section", {}), "clearance": pipe.get("clearance", 0), "movable": pipe.get("movable", False)})

    for cable in cables:
        section = cable.get("cross_section", {})
        half = max(float(section.get("width", 120)), float(section.get("height", 60))) / 2
        points = [point3(p) for p in cable["route_nodes"]]
        objects.append(SceneObject(cable["id"], "CableTray", BBox.from_points(points, half), {"width": section.get("width"), "height": section.get("height"), "clearance": cable.get("clearance", 0), "movable": cable.get("movable", False)}, COLORS["cable"]))
        for idx, (p1, p2) in enumerate(zip(points, points[1:]), start=1):
            objects.append(SceneObject(f"{cable['id']}_SEG_{idx:03d}", "CableTraySegment", segment_bbox(p1, p2, half), {"parent_id": cable["id"]}, COLORS["cable"]))
        centerlines.append({"id": cable["id"], "object_type": "cable_tray", "route_nodes": [list(p) for p in points], "cross_section": section, "clearance": cable.get("clearance", 0), "movable": cable.get("movable", False)})
    return objects, centerlines


def build_equipment(equipment: list[dict[str, Any]]) -> tuple[list[SceneObject], list[dict[str, Any]]]:
    objects: list[SceneObject] = []
    interfaces: list[dict[str, Any]] = []
    for item in equipment:
        origin = point3(item["origin"])
        if item.get("equipment_type", "box") == "box":
            size = point3(item.get("size", [800, 500, 600]))
            bbox = BBox(origin, (origin[0] + size[0], origin[1] + size[1], origin[2] + size[2]))
        elif item.get("equipment_type") == "cylinder":
            radius = float(item.get("diameter", 600)) / 2
            height = float(item.get("height", 900))
            bbox = BBox(origin, (origin[0] + radius * 2, origin[1] + radius * 2, origin[2] + height))
            size = (radius * 2, radius * 2, height)
        else:
            size = point3(item.get("size", [900, 600, 700]))
            bbox = BBox(origin, (origin[0] + size[0], origin[1] + size[1], origin[2] + size[2]))
        properties = {
            "equipment_type": item.get("equipment_type", "box"),
            "weight": item.get("weight", 0),
            "base_point": list(origin),
            "mounting_height": origin[2],
            "ground_clearance": item.get("ground_clearance", origin[2]),
            "local_axes": {"x": [1, 0, 0], "y": [0, 1, 0], "z": [0, 0, 1]},
        }
        objects.append(SceneObject(item["id"], "Equipment", bbox, properties, COLORS["equipment"]))
        face = item.get("mounting_face", {})
        face_shape = face.get("shape_type") or ("circle" if "diameter" in face else "rectangle")
        face_plane = face.get("plane", "xy")
        face_size = face.get("size", [face.get("diameter", size[0]), face.get("diameter", size[1])])
        mounting_features = _resolve_mounting_features(item, origin, size, face_shape, face_size)
        for idx, feature in enumerate(mounting_features, start=1):
            feature_id = f"{item['id']}_MOUNT_FEATURE_{idx:03d}"
            f_origin = point3(feature["origin"])
            if feature["type"] == "circular_boss":
                diameter = float(feature["diameter"])
                objects.append(SceneObject(feature_id, "MountingFeature", BBox((f_origin[0], f_origin[1], f_origin[2]), (f_origin[0] + diameter, f_origin[1] + diameter, f_origin[2] + feature["height"])), {"equipment_id": item["id"], **feature}, COLORS["mounting_marker"]))
            elif feature["type"] in {"circular_mounting_disk", "support_cylinder"}:
                diameter = float(feature["diameter"])
                objects.append(SceneObject(feature_id, "MountingFeature", BBox((f_origin[0], f_origin[1], f_origin[2]), (f_origin[0] + diameter, f_origin[1] + diameter, f_origin[2] + feature["height"])), {"equipment_id": item["id"], **feature}, COLORS["mounting_marker"]))
            elif feature["type"] in {"wall_mounting_plate", "mounting_ear"}:
                f_size = feature["size"]
                thickness = float(feature.get("thickness", 35.0))
                if feature.get("plane") == "yoz":
                    bbox = BBox((f_origin[0], f_origin[1], f_origin[2]), (f_origin[0] + thickness, f_origin[1] + f_size[0], f_origin[2] + f_size[1]))
                else:
                    bbox = BBox((f_origin[0], f_origin[1], f_origin[2]), (f_origin[0] + f_size[0], f_origin[1] + thickness, f_origin[2] + f_size[1]))
                objects.append(SceneObject(feature_id, "MountingFeature", bbox, {"equipment_id": item["id"], **feature}, COLORS["mounting_marker"]))
            else:
                f_size = feature["size"]
                objects.append(SceneObject(feature_id, "MountingFeature", BBox((f_origin[0], f_origin[1], f_origin[2]), (f_origin[0] + f_size[0], f_origin[1] + f_size[1], f_origin[2] + feature["height"])), {"equipment_id": item["id"], **feature}, COLORS["mounting_marker"]))
        holes = []
        for hole in item.get("mounting_holes", []):
            local = point3(hole["local_position"])
            global_position = [origin[0] + local[0], origin[1] + local[1], origin[2] + local[2]]
            holes.append(
                {
                    "id": hole["id"],
                    "marker_id": f"{hole['id']}_HoleMarker",
                    "global_position": global_position,
                    "diameter": hole.get("diameter", 18),
                    "type": hole.get("type", "bolt_hole"),
                    "through_feature_id": _resolve_hole_feature_id(global_position, mounting_features, face_plane),
                }
            )
        face_record = {
            "face_id": face.get("face_id", "MOUNT_FACE_BOTTOM"),
            "interface_element_id": f"{item['id']}_Extract.1",
            "secondary_interface_element_id": f"{item['id']}_Extract.2",
            "joined_interface_element_id": f"{item['id']}_Join.3",
            "shape_type": face_shape,
            "plane": face_plane,
            "origin": list(origin),
            "center": _face_center(origin, face_size, face_plane),
            "normal": face.get("normal", [0, 0, -1]),
            "size": face_size,
        }
        if item.get("equipment_type") == "wall_box":
            face_record["virtual_face_from"] = [feature["id"] for feature in mounting_features if feature["type"] == "mounting_ear"]
        parameters = {
            "equipment_length": size[0],
            "equipment_width": size[1],
            "equipment_height": size[2],
            "equipment_weight": item.get("weight", 0),
            "mounting_face_origin_x": origin[0],
            "mounting_face_origin_y": origin[1],
            "mounting_face_origin_z": origin[2],
            "mounting_face_length": face_size[0],
            "mounting_face_width": face_size[1],
            "mounting_height": origin[2],
            "ground_clearance": item.get("ground_clearance", origin[2]),
        }
        if item.get("equipment_type") == "cylinder":
            parameters["equipment_diameter"] = item.get("diameter", size[0])
        if face_shape == "discrete_pads":
            pads = []
            for idx, pad in enumerate(face.get("pads", []), start=1):
                local_origin = point3(pad.get("origin", [0, 0, 0]))
                pad_size = pad.get("size", [100, 100])
                pad_origin = (origin[0] + local_origin[0], origin[1] + local_origin[1], origin[2] + local_origin[2])
                pad_id = f"{item['id']}_MOUNT_FACE_PAD_{idx:03d}"
                pads.append({"id": pad.get("id", pad_id), "origin": list(pad_origin), "size": pad_size})
                objects.append(SceneObject(pad_id, "MountingFace", BBox((pad_origin[0], pad_origin[1], pad_origin[2] - 1), (pad_origin[0] + pad_size[0], pad_origin[1] + pad_size[1], pad_origin[2] + 1)), {"equipment_id": item["id"], "normal": face.get("normal", [0, 0, -1]), "shape_type": "discrete_pad"}, COLORS["mounting_marker"]))
            face_record["pads"] = pads
        elif face_shape == "circle":
            diameter = float(face.get("diameter", min(face_size)))
            face_record["diameter"] = diameter
            objects.append(SceneObject(f"{item['id']}_MOUNT_FACE", "MountingFace", BBox((origin[0], origin[1], origin[2] - 1), (origin[0] + diameter, origin[1] + diameter, origin[2] + 1)), {"equipment_id": item["id"], "normal": face.get("normal", [0, 0, -1]), "shape_type": "circle"}, COLORS["mounting_marker"]))
        else:
            objects.append(SceneObject(f"{item['id']}_MOUNT_FACE", "MountingFace", BBox((origin[0], origin[1], origin[2] - 1), (origin[0] + face_size[0], origin[1] + face_size[1], origin[2] + 1)), {"equipment_id": item["id"], "normal": face.get("normal", [0, 0, -1]), "shape_type": "rectangle"}, COLORS["mounting_marker"]))
        interfaces.append({"equipment_id": item["id"], "base_point": list(origin), "local_axes": properties["local_axes"], "mounting_face": face_record, "mounting_features": mounting_features, "mounting_holes": holes, "weight": item.get("weight", 0), "mounting_height": origin[2], "ground_clearance": item.get("ground_clearance", origin[2]), "parameters": parameters})
        for hole in holes:
            hp = point3(hole["global_position"])
            r = float(hole["diameter"]) / 2
            objects.append(SceneObject(hole["id"], "MountingHole", BBox((hp[0] - r, hp[1] - r, hp[2] - 1), (hp[0] + r, hp[1] + r, hp[2] + 1)), {"equipment_id": item["id"], "diameter": hole["diameter"]}, COLORS["mounting_marker"]))
    return objects, interfaces


def _resolve_mounting_features(item: dict[str, Any], origin, size, face_shape: str, face_size: list[float]) -> list[dict[str, Any]]:
    if item.get("mounting_features"):
        features = []
        for feature in item["mounting_features"]:
            local_origin = point3(feature.get("origin", [0, 0, 0]))
            copied = dict(feature)
            copied["origin"] = [origin[0] + local_origin[0], origin[1] + local_origin[1], origin[2] + local_origin[2]]
            copied.setdefault("role", "outboard_mounting_plate" if "plate" in copied.get("type", "") or "rail" in copied.get("type", "") else "support")
            features.append(copied)
        return features
    if item.get("equipment_type") == "wall_box" or item.get("mounting_face", {}).get("plane") in {"xoz", "yoz"}:
        plane = item.get("mounting_face", {}).get("plane", "xoz")
        ear_w = 120.0
        ear_h = 170.0
        z0 = origin[2] + size[2] - ear_h
        if plane == "yoz":
            return [
                {"id": "WALL_EAR_LEFT", "type": "mounting_ear", "role": "vertical_mounting_plate", "plane": plane, "origin": [origin[0], origin[1] + 70.0, z0], "size": [ear_w, ear_h], "thickness": 30.0, "height": 30.0, "hole_diameter": 18.0},
                {"id": "WALL_EAR_RIGHT", "type": "mounting_ear", "role": "vertical_mounting_plate", "plane": plane, "origin": [origin[0], origin[1] + size[1] - 70.0 - ear_w, z0], "size": [ear_w, ear_h], "thickness": 30.0, "height": 30.0, "hole_diameter": 18.0},
            ]
        return [
            {"id": "WALL_EAR_LEFT", "type": "mounting_ear", "role": "vertical_mounting_plate", "plane": plane, "origin": [origin[0] + 70.0, origin[1], z0], "size": [ear_w, ear_h], "thickness": 30.0, "height": 30.0, "hole_diameter": 18.0},
            {"id": "WALL_EAR_RIGHT", "type": "mounting_ear", "role": "vertical_mounting_plate", "plane": plane, "origin": [origin[0] + size[0] - 70.0 - ear_w, origin[1], z0], "size": [ear_w, ear_h], "thickness": 30.0, "height": 30.0, "hole_diameter": 18.0},
        ]
    if item.get("equipment_type") == "cylinder" or face_shape == "circle":
        diameter = float(face_size[0])
        support_diameter = float(item.get("support_diameter", diameter * 0.58))
        support_height = float(item.get("support_height", 70.0))
        disk_height = float(item.get("mounting_disk_height", 24.0))
        support_origin = [origin[0] + diameter / 2 - support_diameter / 2, origin[1] + diameter / 2 - support_diameter / 2, origin[2] + disk_height]
        return [
            {"id": "MOUNT_DISK_001", "type": "circular_mounting_disk", "role": "mounting_face", "origin": [origin[0], origin[1], origin[2]], "diameter": diameter, "height": disk_height},
            {"id": "SUPPORT_CYLINDER_001", "type": "support_cylinder", "role": "support", "origin": support_origin, "diameter": support_diameter, "height": support_height},
        ]
    rail_height = 45.0
    rail_width = min(120.0, float(size[1]) * 0.25)
    inset_y = max(40.0, float(size[1]) * 0.08)
    return [
        {"id": "MOUNT_RAIL_001", "type": "rectangular_rail", "role": "outboard_mounting_plate", "origin": [origin[0], origin[1] + inset_y, origin[2]], "size": [size[0], rail_width], "height": rail_height},
        {"id": "MOUNT_RAIL_002", "type": "rectangular_rail", "role": "outboard_mounting_plate", "origin": [origin[0], origin[1] + size[1] - inset_y - rail_width, origin[2]], "size": [size[0], rail_width], "height": rail_height},
    ]


def _resolve_hole_feature_id(global_position: list[float], features: list[dict[str, Any]], face_plane: str) -> str:
    candidates = [feature for feature in features if feature.get("role") in {"outboard_mounting_plate", "vertical_mounting_plate", "mounting_face"}]
    candidates = candidates or features
    x, y, z = global_position
    for feature in candidates:
        origin = feature["origin"]
        if feature["type"] in {"circular_boss", "circular_mounting_disk", "support_cylinder"}:
            d = float(feature["diameter"])
            cx = origin[0] + d / 2
            cy = origin[1] + d / 2
            if (x - cx) ** 2 + (y - cy) ** 2 <= (d / 2) ** 2:
                return feature["id"]
        else:
            size = feature.get("size", [0, 0])
            if face_plane == "xoz":
                if origin[0] <= x <= origin[0] + size[0] and origin[2] <= z <= origin[2] + size[1]:
                    return feature["id"]
            elif face_plane == "yoz":
                if origin[1] <= y <= origin[1] + size[0] and origin[2] <= z <= origin[2] + size[1]:
                    return feature["id"]
            elif origin[0] <= x <= origin[0] + size[0] and origin[1] <= y <= origin[1] + size[1]:
                return feature["id"]
    return candidates[0]["id"] if candidates else ""


def _face_center(origin, face_size: list[float], face_plane: str) -> list[float]:
    if face_plane == "xoz":
        return [origin[0] + face_size[0] / 2, origin[1], origin[2] + face_size[1] / 2]
    if face_plane == "yoz":
        return [origin[0], origin[1] + face_size[0] / 2, origin[2] + face_size[1] / 2]
    return [origin[0] + face_size[0] / 2, origin[1] + face_size[1] / 2, origin[2]]


def build_foundation_zone(zone: dict[str, Any] | None) -> list[SceneObject]:
    if not zone:
        return []
    return [SceneObject(zone.get("id", "FDZ_001"), "FoundationDesignZone", zone_bbox(zone), {"related_equipment": zone.get("related_equipment", "EQ_001"), "size": zone.get("size")}, COLORS["foundation"])]
