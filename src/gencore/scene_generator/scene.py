from __future__ import annotations

from pathlib import Path
from typing import Any

from .builders import build_compartment, build_equipment, build_foundation_zone, build_pipelines
from .core import SceneBundle
from .graph import export_graph
from .io_utils import write_csv, write_json, write_text


def assemble_scene_bundle(config: dict[str, Any]) -> SceneBundle:
    objects = []
    objects.extend(build_compartment(config["compartment"]))
    pipe_objects, centerlines = build_pipelines(config.get("pipes", []), config.get("cables", []))
    equipment_objects, interfaces = build_equipment(config.get("equipment", []))
    objects.extend(pipe_objects)
    objects.extend(equipment_objects)
    objects.extend(build_foundation_zone(config.get("foundation_design_zone")))
    graph = export_graph(objects, config.get("expected_interferences", []))
    bundle = SceneBundle(config, objects, centerlines, interfaces, config.get("expected_interferences", []), graph)
    from .validation import validate_scene

    bundle.validation_report = validate_scene(config, bundle)
    return bundle


def write_case_outputs(bundle: SceneBundle, case_dir: str | Path) -> Path:
    case_path = Path(case_dir)
    config = bundle.scene_config
    write_json(case_path / "input" / "scene_config.json", config)
    write_json(case_path / "input" / "compartment_config.json", config.get("compartment", {}))
    write_json(case_path / "input" / "pipeline_config.json", {"pipes": config.get("pipes", []), "cables": config.get("cables", [])})
    write_json(case_path / "input" / "equipment_config.json", {"equipment": config.get("equipment", [])})
    write_json(case_path / "input" / "expected_interferences.json", config.get("expected_interferences", []))
    write_json(case_path / "graph" / "scene_graph.json", bundle.graph)
    write_json(case_path / "graph" / "object_bounding_boxes.json", bundle.bounding_boxes)
    write_json(case_path / "graph" / "route_centerlines.json", bundle.route_centerlines)
    write_json(case_path / "graph" / "equipment_interfaces.json", bundle.equipment_interfaces)
    write_json(case_path / "reports" / "validation_report.json", bundle.validation_report)
    rows = [{"id": obj.id, "type": obj.type, "bbox_min": obj.bbox.to_dict()["min"], "bbox_max": obj.bbox.to_dict()["max"]} for obj in bundle.objects]
    write_csv(case_path / "reports" / "object_list.csv", rows, ["id", "type", "bbox_min", "bbox_max"])
    summary = f"# {config.get('scene_id')}\n\nValid: {bundle.validation_report['valid']}\n\nObjects: {len(bundle.objects)}\n"
    write_text(case_path / "reports" / "scene_summary.md", summary)
    (case_path / "cad").mkdir(parents=True, exist_ok=True)
    write_text(
        case_path / "cad" / "README.txt",
        "Run scripts/build_catia_scene.py with --output scene.CATProduct to create compartment.CATPart, pipelines.CATPart, equipments/<equipment_id>.CATPart, foundation_zone.CATPart, and scene.CATProduct.\n",
    )
    (case_path / "screenshots").mkdir(parents=True, exist_ok=True)
    return case_path
