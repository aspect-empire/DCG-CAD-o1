from decimal import Decimal

from gencore.foundation_rules.calculator import FoundationCalculator


def valid_input():
    return {
        "equipment_id": "EQ-001",
        "dry_mass_kg": "600",
        "fluid_mass_kg": "50",
        "attached_pipeline_mass_kg": "20",
        "installation_length_mm": "1000",
        "installation_width_mm": "500",
        "moving_equipment": True,
        "in_plane_load": False,
        "hole_diameter_mm": "20",
        "web_height_mm": "200",
        "plate_thickness_mm": "8",
        "cell_area_mm2": "1000",
        "opening_area_mm2": "400",
        "opening_radius_mm": "201",
        "penetration_height_mm": "60",
        "member_height_mm": "100",
        "system_type": "propulsion",
        "premise_event_ids": ["evt:" + "d" * 64],
    }


def test_missing_installation_area_returns_unknown_not_default():
    result = FoundationCalculator().calculate({"equipment_id": "EQ-1", "dry_mass_kg": "600"})

    assert result.status == "unknown"
    assert set(result.missing_inputs) == {"installation_length_mm", "installation_width_mm"}
    assert result.values == {}


def test_force_requires_explicit_conversion_authority():
    data = valid_input()
    data["external_loads"] = [{"direction": "x", "force_N": "980.665"}]

    result = FoundationCalculator().calculate(data)

    assert result.status == "unknown"
    assert "external_loads[0].authorize_force_conversion" in result.missing_inputs


def test_directional_loads_choose_max_and_authorized_force_is_converted():
    data = valid_input()
    data["moving_equipment"] = False
    data["external_loads"] = [
        {"direction": "x", "equivalent_mass_kg": "100"},
        {
            "direction": "y",
            "force_N": "1961.33",
            "authorize_force_conversion": True,
            "gravity_m_s2": "9.80665",
        },
    ]

    result = FoundationCalculator().calculate(data)

    assert result.status == "derived"
    assert Decimal(result.intermediates["selected_total_mass_kg"]) == Decimal("870")
    assert result.intermediates["governing_direction"] == "y"


def test_every_value_has_rule_source_intermediates_and_stable_hash():
    calculator = FoundationCalculator()
    first = calculator.calculate(valid_input())
    second = calculator.calculate(valid_input())
    panel = first.values["panel_thickness_mm"]

    assert first.status == "derived"
    assert panel.state == "derived"
    assert panel.rule_ids == ("adjust.moving.v1", "thickness.unit_area.v1")
    assert "paragraph:34" in panel.source_locators
    assert "table:unit_area_load_thickness" in panel.source_locators
    assert first.intermediates["unit_area_mass_kg_m2"] == "1340"
    assert first.content_hash == first.recompute_hash() == second.content_hash


def test_calculation_result_builds_a_declared_graph_proposal():
    result = FoundationCalculator().calculate(valid_input())

    proposal = result.to_graph_proposal("run-1", "ver:base")

    assert proposal.base_version == "ver:base"
    assert proposal.validation_plan == ("schema", "units", "rules", "write_set")
    assert set(operation.target for operation in proposal.operations) == set(proposal.write_set)
    assert all(operation.value["state"] in {"derived", "unknown", "conflicted"} for operation in proposal.operations)

