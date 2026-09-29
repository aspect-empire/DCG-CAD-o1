from __future__ import annotations

from pathlib import Path
import os
import re

from ..core import SceneBundle
from ..defaults import COLORS
from ..scene import assemble_scene_bundle
from .catia_session import CatiaSession
from .geometry_primitives import create_box, create_circular_pocket_z, create_cylinder_between_points, create_cylinder_z, create_sweep_rectangle_along_polyline, create_transparent_box


def planned_catia_output_paths(output_path: str | Path) -> dict[str, Path]:
    product = Path(output_path).expanduser().resolve()
    if product.suffix.lower() != ".catproduct":
        product = product.with_suffix(".CATProduct")
    cad_dir = product.parent
    return {
        "product": product,
        "compartment": cad_dir / "compartment.CATPart",
        "pipelines": cad_dir / "pipelines.CATPart",
        "equipment_dir": cad_dir / "equipments",
        "legacy_equipments": cad_dir / "equipments.CATPart",
        "foundation_zone": cad_dir / "foundation_zone.CATPart",
    }


def planned_equipment_output_paths(output_path: str | Path, equipment_ids: list[str]) -> dict[str, Path]:
    paths = planned_catia_output_paths(output_path)
    return {equipment_id: paths["equipment_dir"] / f"{_safe_part_file_name(equipment_id)}.CATPart" for equipment_id in equipment_ids}


def build_catia_scene(config: dict, output_path: str | Path, visible: bool = True) -> Path:
    bundle = assemble_scene_bundle(config)
    return build_catia_scene_from_bundle(bundle, output_path, visible=visible)


def build_catia_scene_from_bundle(bundle: SceneBundle, output_path: str | Path, visible: bool = True) -> Path:
    session = CatiaSession(visible=visible)
    paths = planned_catia_output_paths(output_path)
    equipment_by_id = {item["id"]: item for item in bundle.scene_config.get("equipment", [])}
    interface_by_id = {item["equipment_id"]: item for item in bundle.equipment_interfaces}
    equipment_paths = planned_equipment_output_paths(output_path, list(equipment_by_id))
    for path in paths.values():
        if path.suffix:
            path.parent.mkdir(parents=True, exist_ok=True)
        else:
            path.mkdir(parents=True, exist_ok=True)
    session.close_documents_for_paths([paths["product"], paths["foundation_zone"], paths["legacy_equipments"], paths["pipelines"], paths["compartment"], *equipment_paths.values()])
    _remove_stale_legacy_equipment_part(paths["legacy_equipments"])

    component_files = []
    compartment_types = {"Deck", "DeckLongitudinal", "DeckTransverse", "Bulkhead", "BulkheadStiffener"}
    foundation_types = {"FoundationDesignZone"}

    compartment_doc = _build_object_part(session, "compartment", [obj for obj in bundle.objects if obj.type in compartment_types])
    component_files.append(session.save_as(compartment_doc, paths["compartment"]))
    session.close(compartment_doc)

    pipeline_doc = _build_pipeline_part(session, "pipelines", bundle.route_centerlines)
    component_files.append(session.save_as(pipeline_doc, paths["pipelines"]))
    session.close(pipeline_doc)

    for equipment_id, spec in equipment_by_id.items():
        equipment_doc = _build_single_equipment_part(session, equipment_id, spec, interface_by_id[equipment_id])
        component_files.append(session.save_as(equipment_doc, equipment_paths[equipment_id]))
        session.close(equipment_doc)

    foundation_objects = [obj for obj in bundle.objects if obj.type in foundation_types]
    if foundation_objects:
        foundation_doc = _build_object_part(session, "foundation_zone", foundation_objects)
        component_files.append(session.save_as(foundation_doc, paths["foundation_zone"]))
        session.close(foundation_doc)

    product_doc = session.new_product(bundle.scene_config.get("scene_id", "ShipCompartmentScene"))
    _log("assembling CATProduct")
    product_doc.product.products.add_components_from_files(tuple(str(path) for path in component_files), "All")
    product_doc.product.update()
    _log("saving CATProduct")
    product_path = session.save_as(product_doc, paths["product"])
    return product_path


def _build_object_part(session: CatiaSession, name: str, objects) -> object:
    doc = session.new_part(name)
    part = doc.part
    for obj in objects:
        _log(f"building {name}: {obj.type} {obj.id}")
        bbox = obj.bbox.to_dict()
        if obj.type == "FoundationDesignZone":
            create_transparent_box(part, obj.id, bbox, color=obj.color, alpha=0.35)
            continue
        min_pt = bbox["min"]
        max_pt = bbox["max"]
        size = [max_pt[i] - min_pt[i] for i in range(3)]
        create_box(part, obj.id, min_pt, size, color=obj.color)
    part.update()
    return doc


def _build_pipeline_part(session: CatiaSession, name: str, centerlines) -> object:
    doc = session.new_part(name)
    part = doc.part
    for centerline in centerlines:
        _log(f"building {name}: route {centerline['id']}")
        points = centerline["route_nodes"]
        if centerline["object_type"] == "pipe":
            radius = float(centerline["cross_section"].get("diameter", 100)) / 2
            for idx, (p1, p2) in enumerate(zip(points, points[1:]), start=1):
                create_cylinder_between_points(part, f"{centerline['id']}_SEG_{idx:03d}", p1, p2, radius, color=COLORS["pipe"])
        else:
            section = centerline["cross_section"]
            create_sweep_rectangle_along_polyline(part, centerline["id"], points, section.get("width", 160), section.get("height", 80), color=COLORS["cable"])
    part.update()
    return doc


def _build_single_equipment_part(session: CatiaSession, equipment_id: str, spec: dict, interface: dict) -> object:
    doc = session.new_part(equipment_id)
    part = doc.part
    sets = _create_equipment_tree_sets(part)
    size = _equipment_size(spec)
    mounting_set = _mounting_interface_set(sets)
    _log(f"building equipment part: {equipment_id}")
    _create_mounting_feature_geometry(part, equipment_id, interface["mounting_features"])
    _create_equipment_body_geometry(part, equipment_id, spec, interface["mounting_features"])
    _create_equipment_reference_geometry(part, sets, equipment_id, interface, size)
    mounting_face_ref = _create_mounting_face_interface(part, mounting_set, interface["mounting_face"])
    _create_mounting_face_geometry(part, equipment_id, interface["mounting_face"])
    _create_mounting_hole_points(part, mounting_set, interface["mounting_holes"], mounting_face_ref, interface["mounting_features"])
    _create_equipment_parameters(part, equipment_id, interface["parameters"])
    part.update()
    return doc


def _safe_part_file_name(name: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(name)).strip("._")
    return safe or "equipment"


def _remove_stale_legacy_equipment_part(path: Path) -> None:
    try:
        if path.exists():
            path.unlink()
    except Exception:
        pass


def _mounting_interface_set(sets: dict[str, object]) -> object:
    for key, value in sets.items():
        text = str(key)
        if ("安装" in text and "接口" in text) or ("瀹" in text and "鎺" in text):
            return value
    values = list(sets.values())
    return values[4] if len(values) > 4 else values[-1]


def _equipment_size(spec: dict) -> list[float]:
    if spec.get("equipment_type") == "cylinder":
        diameter = float(spec.get("diameter", 600))
        return [diameter, diameter, float(spec.get("height", 900))]
    return list(spec.get("size", [800, 500, 600]))


def _create_mounting_feature_geometry(part, equipment_id: str, features: list[dict]) -> None:
    for idx, feature in enumerate(features, start=1):
        name = f"{equipment_id}_{feature.get('id', f'MOUNT_FEATURE_{idx:03d}')}"
        if feature["type"] in {"circular_boss", "circular_mounting_disk", "support_cylinder"}:
            create_cylinder_z(part, name, feature["origin"], feature["diameter"], feature["height"], color=COLORS["mounting_marker"])
        elif feature["type"] in {"wall_mounting_plate", "mounting_ear"}:
            origin = feature["origin"]
            thickness = float(feature.get("thickness", 35.0))
            if feature.get("plane") == "yoz":
                create_box(part, name, origin, [thickness, feature["size"][0], feature["size"][1]], color=COLORS["mounting_marker"])
            else:
                create_box(part, name, origin, [feature["size"][0], thickness, feature["size"][1]], color=COLORS["mounting_marker"])
        else:
            create_box(part, name, feature["origin"], [feature["size"][0], feature["size"][1], feature["height"]], color=COLORS["mounting_marker"])


def _create_equipment_body_geometry(part, equipment_id: str, spec: dict, features: list[dict]) -> None:
    origin = list(spec["origin"])
    lift = max((float(feature.get("height", 0.0)) for feature in features), default=0.0)
    if spec.get("equipment_type") == "cylinder":
        disk = next((feature for feature in features if feature.get("type") == "circular_mounting_disk"), {})
        support = next((feature for feature in features if feature.get("type") == "support_cylinder"), {})
        lift = float(disk.get("height", 0.0)) + float(support.get("height", 0.0))
    body_origin = [origin[0], origin[1], origin[2] + lift]
    if spec.get("equipment_type") == "cylinder" and disk:
        body_diameter = float(spec.get("diameter", 600))
        disk_diameter = float(disk.get("diameter", body_diameter))
        disk_origin = disk.get("origin", origin)
        disk_center = [float(disk_origin[0]) + disk_diameter / 2, float(disk_origin[1]) + disk_diameter / 2]
        body_origin = [disk_center[0] - body_diameter / 2, disk_center[1] - body_diameter / 2, origin[2] + lift]
    if spec.get("equipment_type") == "wall_box":
        wall_feature = next((feature for feature in features if feature.get("type") in {"wall_mounting_plate", "mounting_ear"}), {})
        thickness = float(wall_feature.get("thickness", 35.0))
        if wall_feature.get("plane") == "yoz":
            body_origin = [origin[0] + thickness, origin[1], origin[2]]
        else:
            body_origin = [origin[0], origin[1] + thickness, origin[2]]
    if spec.get("equipment_type") == "cylinder":
        create_cylinder_z(part, equipment_id, body_origin, spec.get("diameter", 600), spec.get("height", 900), color=COLORS["equipment"])
    else:
        create_box(part, equipment_id, body_origin, spec.get("size", [800, 500, 600]), color=COLORS["equipment"])


def _create_equipment_tree_sets(part) -> dict[str, object]:
    result = {}
    output_set = part.hybrid_bodies.add()
    output_set.name = "输出元素集"
    result["输出元素集"] = output_set
    interface_set = output_set.hybrid_bodies.add()
    interface_set.name = "接口元素集"
    result["接口元素集"] = interface_set
    for name in ["管路接口集", "电缆接口集", "安装接口集"]:
        hb = interface_set.hybrid_bodies.add()
        hb.name = name
        result[name] = hb
    install_set = output_set.hybrid_bodies.add()
    install_set.name = "安装元素集"
    result["安装元素集"] = install_set
    cg_set = output_set.hybrid_bodies.add()
    cg_set.name = "重心元素集"
    result["重心元素集"] = cg_set
    outer_set = output_set.hybrid_bodies.add()
    outer_set.name = "最大外形"
    result["最大外形"] = outer_set
    return result


def _create_equipment_reference_geometry(part, sets: dict[str, object], equipment_id: str, interface: dict, size: list[float]) -> None:
    origin = interface["base_point"]
    hsf = part.hybrid_shape_factory
    base_point = hsf.add_new_point_coord(float(origin[0]), float(origin[1]), float(origin[2]))
    base_point.name = f"{equipment_id}_BasePoint"
    sets["安装元素集"].append_hybrid_shape(base_point)
    base_plane = hsf.add_new_plane_offset(part.origin_elements.plane_xy, float(origin[2]), False)
    base_plane.name = f"{equipment_id}_BasePlane"
    sets["安装元素集"].append_hybrid_shape(base_plane)

    x_end = hsf.add_new_point_coord(float(origin[0]) + 200.0, float(origin[1]), float(origin[2]))
    y_end = hsf.add_new_point_coord(float(origin[0]), float(origin[1]) + 200.0, float(origin[2]))
    z_end = hsf.add_new_point_coord(float(origin[0]), float(origin[1]), float(origin[2]) + 200.0)
    for point, suffix in [(x_end, "XAxisPoint"), (y_end, "YAxisPoint"), (z_end, "ZAxisPoint")]:
        point.name = f"{equipment_id}_{suffix}"
        sets["安装元素集"].append_hybrid_shape(point)
    try:
        base_ref = part.create_reference_from_object(base_point)
        for end_point, suffix in [(x_end, "X Axis"), (y_end, "Y Axis"), (z_end, "Z Axis")]:
            line = hsf.add_new_line_pt_pt(base_ref, part.create_reference_from_object(end_point))
            line.name = f"{equipment_id}_{suffix}"
            sets["安装元素集"].append_hybrid_shape(line)
    except Exception:
        pass
    try:
        axis = part.axis_systems.add()
        axis.name = f"{equipment_id}_AxisSystem"
        axis.put_origin(tuple(float(v) for v in origin))
        axis.put_x_axis((1.0, 0.0, 0.0))
        axis.put_y_axis((0.0, 1.0, 0.0))
    except Exception:
        pass
    cg = [
        float(origin[0]) + float(size[0]) / 2,
        float(origin[1]) + float(size[1]) / 2,
        float(origin[2]) + float(size[2]) / 2,
    ]
    cg_point = hsf.add_new_point_coord(cg[0], cg[1], cg[2])
    cg_point.name = f"{equipment_id}_CenterOfGravity"
    sets["重心元素集"].append_hybrid_shape(cg_point)


def _create_mounting_face_geometry(part, equipment_id: str, face: dict) -> None:
    shape_type = face.get("shape_type", "rectangle")
    if shape_type == "discrete_pads":
        for idx, pad in enumerate(face.get("pads", []), start=1):
            create_box(part, f"{equipment_id}_{pad['id']}", pad["origin"], [pad["size"][0], pad["size"][1], 2.0], color=COLORS["mounting_marker"])


def _create_mounting_face_interface(part, mounting_set, face: dict):
    hsf = part.hybrid_shape_factory
    origin = face["origin"]
    if face.get("plane") == "xoz":
        plane = hsf.add_new_plane_offset(part.origin_elements.plane_zx, float(origin[1]), False)
    elif face.get("plane") == "yoz":
        plane = hsf.add_new_plane_offset(part.origin_elements.plane_yz, float(origin[0]), False)
    else:
        plane = hsf.add_new_plane_offset(part.origin_elements.plane_xy, float(origin[2]), False)
    plane.name = face.get("interface_element_id", "Extract.1")
    mounting_set.append_hybrid_shape(plane)
    try:
        origin_point = hsf.add_new_point_coord(float(origin[0]), float(origin[1]), float(origin[2]))
        origin_point.name = face.get("secondary_interface_element_id", "Extract.2")
        mounting_set.append_hybrid_shape(origin_point)
    except Exception:
        pass
    try:
        join_point = hsf.add_new_point_coord(float(face["center"][0]), float(face["center"][1]), float(face["center"][2]))
        join_point.name = face.get("joined_interface_element_id", "Join.3")
        mounting_set.append_hybrid_shape(join_point)
    except Exception:
        pass
    part.update()
    return part.create_reference_from_object(plane)


def _create_mounting_hole_points(part, mounting_set, holes: list[dict], mounting_face_ref=None, mounting_features: list[dict] | None = None) -> None:
    hsf = part.hybrid_shape_factory
    features_by_id = {feature["id"]: feature for feature in (mounting_features or [])}
    for hole in holes:
        point = hsf.add_new_point_coord(float(hole["global_position"][0]), float(hole["global_position"][1]), float(hole["global_position"][2]))
        point.name = hole["id"]
        mounting_set.append_hybrid_shape(point)
        if mounting_face_ref is not None:
            try:
                circle = hsf.add_new_circle_ctr_rad(part.create_reference_from_object(point), mounting_face_ref, False, float(hole["diameter"]) / 2)
                circle.name = hole.get("marker_id", f"{hole['id']}_HoleMarker")
                mounting_set.append_hybrid_shape(circle)
            except Exception:
                pass
        feature = features_by_id.get(hole.get("through_feature_id"))
        if feature and feature.get("type") not in {"wall_mounting_plate", "mounting_ear"}:
            try:
                z_top = float(feature["origin"][2]) + float(feature.get("height", 0.0))
                create_circular_pocket_z(part, f"{hole['id']}_THROUGH_HOLE", (hole["global_position"][0], hole["global_position"][1]), hole["diameter"], z_top, float(feature.get("height", 0.0)) + 2.0)
            except Exception:
                pass


def _create_equipment_parameters(part, equipment_id: str, parameters: dict[str, float]) -> None:
    params = part.parameters
    try:
        params.create_set_of_parameters(params.root_parameter_set)
    except Exception:
        pass
    for name, value in parameters.items():
        param_name = f"{equipment_id}\\接口参数集\\{name}"
        try:
            if name.endswith("_weight"):
                params.create_real(param_name, float(value))
            else:
                params.create_dimension(param_name, "LENGTH", float(value))
        except Exception:
            try:
                params.create_real(param_name.replace("\\", "_"), float(value))
            except Exception:
                pass


def _log(message: str) -> None:
    if os.environ.get("SCG_CATIA_VERBOSE") == "1":
        print(f"[catia] {message}", flush=True)
        try:
            log_path = Path("outputs/catia_build_progress.log")
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with log_path.open("a", encoding="utf-8") as fh:
                fh.write(message + "\n")
        except Exception:
            pass
