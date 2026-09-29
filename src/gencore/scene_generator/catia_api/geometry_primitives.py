from __future__ import annotations

from math import atan2, degrees, hypot
from typing import Iterable

from .material_and_color import apply_color, apply_transparency

_PLANE_CACHE = {}


def create_box(part, name, origin, size, color=None):
    """Create an axis-aligned box by sketching on XY and padding in +Z."""
    x, y, z = map(float, origin)
    lx, ly, lz = map(float, size)
    body = part.main_body
    body.name = getattr(body, "name", "PartBody")
    plane = _plane_xy_at_z(part, z)
    part.in_work_object = body
    sketch = body.sketches.add(plane)
    sketch.name = f"{name}_profile"
    factory = sketch.open_edition()
    factory.create_line(x, y, x + lx, y)
    factory.create_line(x + lx, y, x + lx, y + ly)
    factory.create_line(x + lx, y + ly, x, y + ly)
    factory.create_line(x, y + ly, x, y)
    sketch.close_edition()
    part.in_work_object = body
    pad = part.shape_factory.add_new_pad(sketch, lz)
    pad.name = name
    return apply_color(pad, color)


def create_cylinder_z(part, name, origin, diameter, height, color=None):
    x, y, z = map(float, origin)
    radius = float(diameter) / 2.0
    body = part.main_body
    plane = _plane_xy_at_z(part, z)
    part.in_work_object = body
    sketch = body.sketches.add(plane)
    sketch.name = f"{name}_profile"
    factory = sketch.open_edition()
    factory.create_closed_circle(x + radius, y + radius, radius)
    sketch.close_edition()
    part.in_work_object = body
    pad = part.shape_factory.add_new_pad(sketch, float(height))
    pad.name = name
    return apply_color(pad, color)


def create_circular_pocket_z(part, name, center, diameter, z_top, depth):
    x, y = float(center[0]), float(center[1])
    body = part.main_body
    plane = _plane_xy_at_z(part, float(z_top))
    part.in_work_object = body
    sketch = body.sketches.add(plane)
    sketch.name = f"{name}_profile"
    factory = sketch.open_edition()
    factory.create_closed_circle(x, y, float(diameter) / 2.0)
    sketch.close_edition()
    part.in_work_object = body
    pocket = part.shape_factory.add_new_pocket(sketch, float(depth))
    pocket.name = name
    return pocket


def create_plate(part, name, center, length, height, thickness, orientation="xy", color=None):
    cx, cy, cz = map(float, center)
    if orientation in {"xy", "deck"}:
        origin = (cx - length / 2, cy - height / 2, cz)
        size = (length, height, thickness)
    elif orientation == "xz":
        origin = (cx - length / 2, cy - thickness / 2, cz)
        size = (length, thickness, height)
    else:
        origin = (cx - thickness / 2, cy - length / 2, cz)
        size = (thickness, length, height)
    return create_box(part, name, origin, size, color=color)


def create_cylinder_between_points(part, name, p1, p2, radius, color=None):
    """Create a cylinder-like segment. Z-axis segments are true cylinders; others use a box proxy."""
    x1, y1, z1 = map(float, p1)
    x2, y2, z2 = map(float, p2)
    if abs(x1 - x2) < 1e-6 and abs(y1 - y2) < 1e-6:
        return create_cylinder_z(part, name, (x1 - radius, y1 - radius, z1), radius * 2, z2 - z1, color=color)
    length_xy = hypot(x2 - x1, y2 - y1)
    length = hypot(length_xy, z2 - z1)
    # CATIA orientation by arbitrary vector is COM-version sensitive; Phase 1 uses an envelope proxy.
    min_x, min_y, min_z = min(x1, x2) - radius, min(y1, y2) - radius, min(z1, z2) - radius
    size = (abs(x2 - x1) + 2 * radius, abs(y2 - y1) + 2 * radius, abs(z2 - z1) + 2 * radius)
    obj = create_box(part, name, (min_x, min_y, min_z), size, color=color)
    try:
        obj.description = f"cylinder proxy length={length:.3f}, angle_xy={degrees(atan2(y2-y1, x2-x1)):.3f}"
    except Exception:
        pass
    return obj


def create_sweep_circle_along_polyline(part, name, points, radius, color=None):
    created = []
    pts = list(points)
    for idx, (p1, p2) in enumerate(zip(pts, pts[1:]), start=1):
        created.append(create_cylinder_between_points(part, f"{name}_SEG_{idx:03d}", p1, p2, radius, color=color))
    for idx, point in enumerate(pts[1:-1], start=1):
        created.append(create_sphere(part, f"{name}_ELBOW_{idx:03d}", point, radius, color=color))
    return created


def create_sweep_rectangle_along_polyline(part, name, points, width, height, color=None):
    created = []
    half_w = float(width) / 2
    half_h = float(height) / 2
    pts = list(points)
    for idx, (p1, p2) in enumerate(zip(pts, pts[1:]), start=1):
        min_x = min(p1[0], p2[0]) - half_w
        min_y = min(p1[1], p2[1]) - half_w
        min_z = min(p1[2], p2[2]) - half_h
        size = (abs(p2[0] - p1[0]) + width, abs(p2[1] - p1[1]) + width, abs(p2[2] - p1[2]) + height)
        created.append(create_box(part, f"{name}_SEG_{idx:03d}", (min_x, min_y, min_z), size, color=color))
    return created


def create_sphere(part, name, center, radius, color=None):
    # Simplified Phase 1 elbow marker as a cube envelope.
    x, y, z = map(float, center)
    r = float(radius)
    return create_box(part, name, (x - r, y - r, z - r), (2 * r, 2 * r, 2 * r), color=color)


def create_transparent_box(part, name, bbox, color=None, alpha=0.35):
    min_pt = bbox["min"] if isinstance(bbox, dict) else bbox.min
    max_pt = bbox["max"] if isinstance(bbox, dict) else bbox.max
    size = tuple(max_pt[i] - min_pt[i] for i in range(3))
    obj = create_box(part, name, min_pt, size, color=color)
    apply_transparency(obj, alpha)
    return obj


def create_axis_marker(part, name, origin, direction):
    ox, oy, oz = map(float, origin)
    dx, dy, dz = map(float, direction)
    return create_cylinder_between_points(part, name, (ox, oy, oz), (ox + dx, oy + dy, oz + dz), 5.0, color=[30, 30, 30])


def _try_set_offset_z(part, feature, z: float) -> None:
    # Kept for backwards compatibility with early adapter drafts.
    try:
        if abs(float(z)) > 1e-6:
            feature.name = f"{feature.name}_z{float(z):.0f}"
    except Exception:
        pass


def _plane_xy_at_z(part, z: float):
    if abs(float(z)) < 1e-6:
        return part.origin_elements.plane_xy
    key = (id(part.com_object), round(float(z), 6))
    if key in _PLANE_CACHE:
        return _PLANE_CACHE[key]
    try:
        hybrid_bodies = part.hybrid_bodies
        try:
            construction = hybrid_bodies.item("SceneGeneratorConstruction")
        except Exception:
            construction = hybrid_bodies.add()
            construction.name = "SceneGeneratorConstruction"
        plane = part.hybrid_shape_factory.add_new_plane_offset(part.origin_elements.plane_xy, float(z), False)
        plane.name = f"XY_offset_{float(z):.3f}"
        construction.append_hybrid_shape(plane)
        part.update()
        ref = part.create_reference_from_object(plane)
        _PLANE_CACHE[key] = ref
        return ref
    except Exception:
        return part.origin_elements.plane_xy
