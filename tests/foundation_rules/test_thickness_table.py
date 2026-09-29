from decimal import Decimal

import pytest

from gencore.foundation_rules.evaluator import thickness_for_load


@pytest.mark.parametrize(
    "load,panel,web",
    [
        ("0", "3", "3"),
        ("60", "3", "3"),
        ("60.0001", "4", "3"),
        ("100", "4", "3"),
        ("100.0001", "5", "4"),
        ("300", "5", "4"),
        ("300.0001", "6", "5"),
        ("500", "6", "5"),
        ("500.0001", "8", "6"),
        ("1000", "8", "6"),
        ("1000.0001", "10", "8"),
        ("2000", "10", "8"),
        ("2000.0001", "12", "10"),
        ("5000", "12", "10"),
        ("5000.0001", "16", "12"),
        ("10000", "16", "12"),
        ("10000.0001", "20", "16"),
    ],
)
def test_all_decision_table_boundaries(load, panel, web):
    result = thickness_for_load(load)

    assert result.panel_mm == Decimal(panel)
    assert result.web_bracket_mm == Decimal(web)


def test_moving_and_in_plane_increases_do_not_stack():
    result = thickness_for_load("100", moving=True, in_plane_load=True)

    assert result.panel_mm == Decimal("5")
    assert result.web_bracket_mm == Decimal("4")
    assert result.adjustments == ("in_plane_load", "moving_equipment")


def test_negative_load_is_rejected():
    with pytest.raises(ValueError, match="nonnegative"):
        thickness_for_load("-0.1")

