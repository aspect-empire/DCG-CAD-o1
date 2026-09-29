from __future__ import annotations

from dataclasses import dataclass, field
from math import sqrt
from typing import Any

Point3 = tuple[float, float, float]


def point3(value: list[float] | tuple[float, float, float]) -> Point3:
    return (float(value[0]), float(value[1]), float(value[2]))


@dataclass(frozen=True)
class BBox:
    min: Point3
    max: Point3

    @classmethod
    def from_origin_size(cls, origin: Point3, size: Point3) -> "BBox":
        return cls(origin, (origin[0] + size[0], origin[1] + size[1], origin[2] + size[2]))

    @classmethod
    def from_points(cls, points: list[Point3], margin: float = 0.0) -> "BBox":
        xs, ys, zs = zip(*points)
        return cls(
            (min(xs) - margin, min(ys) - margin, min(zs) - margin),
            (max(xs) + margin, max(ys) + margin, max(zs) + margin),
        )

    def overlaps(self, other: "BBox") -> bool:
        return all(self.min[i] <= other.max[i] and self.max[i] >= other.min[i] for i in range(3))

    def contains_xy(self, other: "BBox") -> bool:
        return (
            self.min[0] <= other.min[0] <= other.max[0] <= self.max[0]
            and self.min[1] <= other.min[1] <= other.max[1] <= self.max[1]
        )

    def to_dict(self) -> dict[str, list[float]]:
        return {"min": list(self.min), "max": list(self.max)}


@dataclass
class SceneObject:
    id: str
    type: str
    bbox: BBox
    properties: dict[str, Any] = field(default_factory=dict)
    color: list[int] | None = None

    def to_bbox_record(self) -> dict[str, Any]:
        return {"id": self.id, "type": self.type, "bbox": self.bbox.to_dict()}

    def to_graph_node(self) -> dict[str, Any]:
        return {"id": self.id, "type": self.type, "properties": dict(self.properties)}


@dataclass
class SceneBundle:
    scene_config: dict[str, Any]
    objects: list[SceneObject]
    route_centerlines: list[dict[str, Any]]
    equipment_interfaces: list[dict[str, Any]]
    expected_interferences: list[dict[str, Any]]
    graph: dict[str, Any]
    validation_report: dict[str, Any] | None = None

    @property
    def bounding_boxes(self) -> list[dict[str, Any]]:
        return [obj.to_bbox_record() for obj in self.objects]


def segment_bbox(p1: Point3, p2: Point3, radius_or_half_extent: float) -> BBox:
    return BBox.from_points([p1, p2], margin=radius_or_half_extent)


def distance(p1: Point3, p2: Point3) -> float:
    return sqrt(sum((p2[i] - p1[i]) ** 2 for i in range(3)))


def zone_bbox(zone: dict[str, Any]) -> BBox:
    center = point3(zone["center"])
    size = point3(zone["size"])
    return BBox(
        (center[0] - size[0] / 2, center[1] - size[1] / 2, center[2] - size[2] / 2),
        (center[0] + size[0] / 2, center[1] + size[1] / 2, center[2] + size[2] / 2),
    )
