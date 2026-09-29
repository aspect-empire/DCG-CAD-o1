import json
from copy import deepcopy
from pathlib import Path

import pytest

from gencore.foundation_rules.compiler import RuleCompilationError, compile_rule_package, load_default_package
from gencore.resources import foundation_resource_root


RULE_ROOT = foundation_resource_root()


def source_data():
    return (
        json.loads((RULE_ROOT / "sources/source_manifest.json").read_text(encoding="utf-8")),
        json.loads((RULE_ROOT / "sources/clause_inventory.json").read_text(encoding="utf-8")),
    )


def test_default_package_has_verified_sources_and_stable_hash():
    package = load_default_package()

    assert package.package_id == "foundation-rules:v1"
    assert package.content_hash == package.recompute_hash()
    assert {rule["rule_id"] for rule in package.rules} >= {
        "thickness.unit_area.v1",
        "adjust.moving.v1",
        "adjust.in_plane.v1",
        "adjust.non_stacking.v1",
    }


def test_duplicate_rule_ids_are_rejected():
    raw = json.loads((RULE_ROOT / "packages/foundation_rules_v1.json").read_text(encoding="utf-8"))
    raw["rules"].append(deepcopy(raw["rules"][0]))
    manifest, inventory = source_data()

    with pytest.raises(RuleCompilationError, match="duplicate rule_id"):
        compile_rule_package(raw, manifest, inventory)


def test_lower_priority_rule_cannot_override_updated_explicit_scope():
    raw = json.loads((RULE_ROOT / "packages/foundation_rules_v1.json").read_text(encoding="utf-8"))
    lower = deepcopy(raw["rules"][0])
    lower.update({"rule_id": "legacy.thickness", "source_clause_id": "D01-T01", "priority": 10})
    raw["rules"].append(lower)
    manifest, inventory = source_data()

    with pytest.raises(RuleCompilationError, match="lower-priority override"):
        compile_rule_package(raw, manifest, inventory)
