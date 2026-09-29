from decimal import Decimal

import pytest

from gencore.foundation_rules import DimensionError, Quantity


def test_force_is_not_silently_added_to_mass():
    with pytest.raises(DimensionError, match="mass.*force|force.*mass"):
        Quantity("100", "kg") + Quantity("980.665", "N")


def test_authorized_force_conversion_requires_gravity():
    force = Quantity("980.665", "N")

    mass = force.equivalent_mass(Quantity("9.80665", "m/s2"))

    assert mass.value == Decimal("100")
    assert mass.unit == "kg"


def test_compatible_lengths_are_added_in_left_hand_unit():
    result = Quantity("1000", "mm") + Quantity("1", "m")

    assert result.value == Decimal("2000")
    assert result.unit == "mm"


def test_unknown_unit_is_rejected():
    with pytest.raises(DimensionError, match="unsupported unit"):
        Quantity("1", "kgf")

