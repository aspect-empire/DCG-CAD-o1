from __future__ import annotations

import json
from pathlib import Path

from gencore.scene_generator.scene import assemble_scene_bundle


def test_synthetic_scene_exposes_one_equipment_interface_with_four_holes() -> None:
    root = Path(__file__).resolve().parents[1]
    config = json.loads(
        (root / "examples" / "basic_case" / "scene.json").read_text(encoding="utf-8")
    )
    bundle = assemble_scene_bundle(config)

    assert bundle.validation_report["valid"] is True
    assert len(bundle.equipment_interfaces) == 1
    assert bundle.equipment_interfaces[0]["equipment_id"] == "EQ_SYNTHETIC"
    assert len(bundle.equipment_interfaces[0]["mounting_holes"]) == 4
