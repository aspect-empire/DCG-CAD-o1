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


def test_geometry_constraints_are_calculated_from_rule_boundaries():
    result = FoundationCalculator().calculate(valid_input())
    constraints = result.constraints

    assert constraints["hole_free_edge_min_mm"].value == "40"
    assert constraints["support_hole_distance_min_mm"].value == "30.0"
    assert constraints["support_hole_distance_max_mm"].value == "60"
    assert constraints["bracket_spacing_min_mm"].value == "200"
    assert constraints["drainage_hole_min_mm"].value == "20"
    assert constraints["drainage_hole_max_mm"].value == "50"
    assert constraints["opening_area_max_mm2"].value == "500.0"
    assert constraints["edge_flat_bar_required"].value is True
    assert constraints["opening_edge_distance_min_mm"].value == "160"
    assert constraints["direct_opening_max_size_mm"].value == "80"
    assert constraints["direct_opening_clearance_min_exclusive_mm"].value == "160"
    assert constraints["doubler_required"].value is True
    assert constraints["propulsion_member_distance_min_mm"].value == "40"
    assert constraints["propulsion_member_distance_max_mm"].value == "50.0"


def test_impossible_drainage_range_is_reported_as_conflicted():
    data = valid_input()
    data["web_height_mm"] = "60"

    result = FoundationCalculator().calculate(data)

    assert result.status == "conflicted"
    assert "drainage_hole_range" in result.conflicts
    assert result.constraints["drainage_hole_max_mm"].state == "conflicted"


def test_absent_optional_geometry_emits_validation_requests_not_guesses():
    data = valid_input()
    for key in ("hole_diameter_mm", "cell_area_mm2", "opening_area_mm2", "plate_thickness_mm"):
        data.pop(key)

    result = FoundationCalculator().calculate(data)

    assert result.status == "derived"
    assert "hole_geometry" in result.validation_requests
    assert "opening_geometry" in result.validation_requests
