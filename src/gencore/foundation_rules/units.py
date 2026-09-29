"""Strict Decimal quantities for deterministic foundation calculations."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


class DimensionError(ValueError):
    """Raised when an operation mixes incompatible engineering dimensions."""


# unit -> (dimension, multiplier to the dimension's canonical unit)
_UNITS = {
    "kg": ("mass", Decimal("1")),
    "N": ("force", Decimal("1")),
    "mm": ("length", Decimal("0.001")),
    "cm": ("length", Decimal("0.01")),
    "m": ("length", Decimal("1")),
    "m/s2": ("acceleration", Decimal("1")),
    "N*m": ("moment", Decimal("1")),
}


@dataclass(frozen=True)
class Quantity:
    value: Decimal
    unit: str

    def __init__(self, value: Decimal | str | int | float, unit: str):
        if unit not in _UNITS:
            raise DimensionError(f"unsupported unit: {unit}")
        object.__setattr__(self, "value", Decimal(str(value)))
        object.__setattr__(self, "unit", unit)

    @property
    def dimension(self) -> str:
        return _UNITS[self.unit][0]

    def to(self, unit: str) -> "Quantity":
        if unit not in _UNITS:
            raise DimensionError(f"unsupported unit: {unit}")
        target_dimension, target_factor = _UNITS[unit]
        if target_dimension != self.dimension:
            raise DimensionError(f"cannot convert {self.dimension} to {target_dimension}")
        base_value = self.value * _UNITS[self.unit][1]
        return Quantity(base_value / target_factor, unit)

    def __add__(self, other: "Quantity") -> "Quantity":
        if self.dimension != other.dimension:
            raise DimensionError(f"cannot add {self.dimension} and {other.dimension}")
        converted = other.to(self.unit)
        return Quantity(self.value + converted.value, self.unit)

    def equivalent_mass(self, gravity: "Quantity") -> "Quantity":
        if self.dimension != "force" or gravity.dimension != "acceleration" or gravity.value <= 0:
            raise DimensionError("force conversion requires positive gravity in m/s2")
        force_n = self.to("N").value
        acceleration = gravity.to("m/s2").value
        return Quantity(force_n / acceleration, "kg")

    def to_dict(self) -> dict[str, str]:
        return {"value": str(self.value), "unit": self.unit, "dimension": self.dimension}
