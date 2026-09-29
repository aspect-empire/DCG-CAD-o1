from __future__ import annotations

import os


def apply_color(catia_object, rgb: list[int] | tuple[int, int, int] | None):
    if not rgb:
        return catia_object
    if not _catia_color_enabled():
        return catia_object
    try:
        from pycatia import catia

        selection = catia().active_document.selection
        selection.clear()
        selection.add(catia_object)
        vis = selection.vis_properties
        vis.set_real_color(int(rgb[0]), int(rgb[1]), int(rgb[2]), 0)
        selection.clear()
    except Exception:
        pass
    return catia_object


def apply_transparency(catia_object, alpha: float):
    if not _catia_color_enabled():
        return catia_object
    try:
        from pycatia import catia

        selection = catia().active_document.selection
        selection.clear()
        selection.add(catia_object)
        selection.vis_properties.set_real_opacity(int((1.0 - alpha) * 255), 0)
        selection.clear()
    except Exception:
        pass
    return catia_object


def _catia_color_enabled() -> bool:
    value = os.environ.get("SCG_APPLY_CATIA_COLOR", "1").strip().lower()
    return value not in {"0", "false", "no", "off"}
