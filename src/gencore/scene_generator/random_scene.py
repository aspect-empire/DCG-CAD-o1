from __future__ import annotations

import random
from typing import Any


LEVELS = {
    "L1": {"pipes": (0, 1), "cables": (0, 1), "density": "low"},
    "L2": {"pipes": (1, 3), "cables": (1, 2), "density": "medium"},
    "L3": {"pipes": (2, 5), "cables": (1, 3), "density": "high"},
    "L4": {"pipes": (4, 8), "cables": (2, 4), "density": "high"},
}


def generate_scene_config(level: str, task: str, index: int, seed: int) -> dict[str, Any]:
    rng = random.Random(f"{seed}:{level}:{task}:{index}")
    length = rng.choice([5600, 6000, 6400])
    width = rng.choice([3600, 4000, 4400])
    eq_size = [900, 600, 700]
    eq_origin = [length / 2 - eq_size[0] / 2 + rng.randint(-300, 300), width / 2 - eq_size[1] / 2 + rng.randint(-200, 200), 500]
    fdz_center = [eq_origin[0] + eq_size[0] / 2, eq_origin[1] + eq_size[1] / 2, 250]
    fdz = {"id": "FDZ_001", "center": fdz_center, "size": [1200, 800, 500], "related_equipment": "EQ_001"}
    config: dict[str, Any] = {
        "scene_id": f"{level}_{task}_{index:04d}",
        "level": level,
        "task_type": task,
        "compartment": {
            "shape_type": "rectangular",
            "deck": {"id": "DECK_001", "origin": [0, 0, 0], "length_x": length, "width_y": width, "thickness": 20, "shape_type": "rectangular"},
            "deck_longitudinals": {"enabled": True, "y_positions": _positions(600, width - 400, 600), "height": 160, "thickness": 12},
            "deck_transverses": {"enabled": True, "x_positions": _positions(1000, length - 800, 1200), "height": 180, "thickness": 14},
            "bulkheads": [
                {"id": "BH_001", "orientation": "x", "position": 0, "height": 1600, "thickness": 20},
                {"id": "BH_002", "orientation": "x", "position": width, "height": 1600, "thickness": 20},
            ],
            "bulkhead_stiffeners": [{"bulkhead_id": "BH_001", "positions": _positions(600, length - 600, 800), "height": 1600, "width": 80, "thickness": 12}],
        },
        "equipment": [_equipment(eq_origin, eq_size)],
        "foundation_design_zone": fdz,
        "pipes": [],
        "cables": [],
        "expected_interferences": [],
    }
    if task == "T2":
        config["pipes"].append(_interference_pipe(fdz))
        config["expected_interferences"].append({"type": "pipe_cross_foundation_web", "object_id": "PIPE_001", "target_zone": "FDZ_001", "expected_repair": "generate_pipe_hole"})
    elif level != "L1" or rng.random() > 0.5:
        config["pipes"].append(_side_pipe(width, length, "PIPE_001"))
    if task != "T1" or level in {"L2", "L3", "L4"}:
        config["cables"].append(_cable(width, length, "CABLE_001"))
    if task == "T3":
        second = [min(length - 1200, eq_origin[0] + 1300), eq_origin[1], 500]
        config["equipment"].append(_equipment(second, eq_size, "EQ_002"))
    return config


def _positions(start: int, stop: float, step: int) -> list[int]:
    return [int(v) for v in range(start, int(stop) + 1, step)]


def _equipment(origin: list[float], size: list[float], obj_id: str = "EQ_001") -> dict[str, Any]:
    return {
        "id": obj_id,
        "equipment_type": "box",
        "origin": origin,
        "size": size,
        "weight": 350,
        "ground_clearance": origin[2],
        "mounting_face": {"face_id": "MOUNT_FACE_BOTTOM", "plane": "bottom", "shape_type": "rectangle", "normal": [0, 0, -1], "size": [size[0], size[1]]},
        "mounting_holes": [
            {"id": f"{obj_id}_EH_001", "local_position": [130, 100, 0], "diameter": 18},
            {"id": f"{obj_id}_EH_002", "local_position": [size[0] - 130, 100, 0], "diameter": 18},
            {"id": f"{obj_id}_EH_003", "local_position": [130, size[1] - 100, 0], "diameter": 18},
            {"id": f"{obj_id}_EH_004", "local_position": [size[0] - 130, size[1] - 100, 0], "diameter": 18},
        ],
    }


def _interference_pipe(fdz: dict[str, Any]) -> dict[str, Any]:
    cx, cy, cz = fdz["center"]
    return {"id": "PIPE_001", "object_type": "pipe", "route_nodes": [[cx - 800, cy, cz + 10], [cx + 800, cy, cz + 10]], "cross_section": {"type": "circle", "diameter": 120}, "clearance": 30, "movable": False}


def _side_pipe(width: float, length: float, obj_id: str) -> dict[str, Any]:
    return {"id": obj_id, "object_type": "pipe", "route_nodes": [[500, width * 0.25, 450], [length - 500, width * 0.25, 450]], "cross_section": {"type": "circle", "diameter": 100}, "clearance": 30, "movable": False}


def _cable(width: float, length: float, obj_id: str) -> dict[str, Any]:
    return {"id": obj_id, "object_type": "cable_tray", "route_nodes": [[800, width * 0.75, 520], [length - 800, width * 0.75, 520]], "cross_section": {"type": "rectangle", "width": 160, "height": 80}, "clearance": 50, "movable": False}
