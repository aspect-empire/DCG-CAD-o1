from __future__ import annotations

from .defaults import COLORS, UNITS


def default_colors() -> dict[str, list[int]]:
    return dict(COLORS)


def default_units() -> dict[str, str]:
    return dict(UNITS)
