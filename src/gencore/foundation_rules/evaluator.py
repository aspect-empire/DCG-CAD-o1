"""Deterministic evaluation of compiled foundation decision tables."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .compiler import CompiledRulePackage, load_default_package


@dataclass(frozen=True)
class ThicknessDecision:
    band_index: int
    panel_mm: Decimal
    web_bracket_mm: Decimal
    adjustments: tuple[str, ...]
    rule_ids: tuple[str, ...]


def thickness_for_load(
    load: Decimal | str | int | float,
    moving: bool = False,
    in_plane_load: bool = False,
    *,
    package: CompiledRulePackage | None = None,
) -> ThicknessDecision:
    value = Decimal(str(load))
    if value < 0:
        raise ValueError("load metric must be nonnegative")
    compiled = package or load_default_package()
    table_rule = compiled.rule("thickness.unit_area.v1")
    bands = table_rule["expression"]["bands"]
    base_index = next(
        index
        for index, band in enumerate(bands)
        if band["upper_inclusive"] is None or value <= Decimal(str(band["upper_inclusive"]))
    )
    adjustments = tuple(sorted(
        name
        for active, name in ((moving, "moving_equipment"), (in_plane_load, "in_plane_load"))
        if active
    ))
    selected_index = min(base_index + int(bool(adjustments)), len(bands) - 1)
    selected = bands[selected_index]
    rule_ids = ["thickness.unit_area.v1"]
    if moving:
        rule_ids.append("adjust.moving.v1")
    if in_plane_load:
        rule_ids.append("adjust.in_plane.v1")
    if len(adjustments) > 1:
        rule_ids.append("adjust.non_stacking.v1")
    return ThicknessDecision(
        selected_index,
        Decimal(str(selected["panel_mm"])),
        Decimal(str(selected["web_bracket_mm"])),
        adjustments,
        tuple(rule_ids),
    )
