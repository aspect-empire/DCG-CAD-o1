"""Source-grounded deterministic foundation parameter calculator."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from gencore.design_state import DesignNode, EvidenceRef, GraphOperation, GraphProposal, ValueState, View
from gencore.design_state.records import _freeze, _thaw
from gencore.events import canonical_hash

from .compiler import CompiledRulePackage, load_default_package
from .evaluator import thickness_for_load
from .explanation import DerivationStep
from .units import Quantity


def _decimal_text(value: Decimal) -> str:
    return format(value, "f")


@dataclass(frozen=True)
class ParameterDecision:
    value: str | bool
    unit: str
    state: str
    rule_ids: tuple[str, ...]
    source_locators: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "unit": self.unit,
            "state": self.state,
            "rule_ids": list(self.rule_ids),
            "source_locators": list(self.source_locators),
        }


@dataclass(frozen=True)
class CalculationResult:
    equipment_id: str
    status: str
    values: Mapping[str, ParameterDecision] = field(default_factory=dict)
    constraints: Mapping[str, ParameterDecision] = field(default_factory=dict)
    intermediates: Mapping[str, Any] = field(default_factory=dict)
    missing_inputs: tuple[str, ...] = ()
    conflicts: tuple[str, ...] = ()
    advisory: tuple[str, ...] = ()
    validation_requests: tuple[str, ...] = ()
    premise_event_ids: tuple[str, ...] = ()
    derivations: tuple[DerivationStep, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "values", MappingProxyType(dict(self.values)))
        object.__setattr__(self, "constraints", MappingProxyType(dict(self.constraints)))
        object.__setattr__(self, "intermediates", _freeze(self.intermediates))
        for name in ("missing_inputs", "conflicts", "advisory", "validation_requests", "premise_event_ids", "derivations"):
            object.__setattr__(self, name, tuple(getattr(self, name)))

    def semantic_dict(self) -> dict[str, Any]:
        return {
            "equipment_id": self.equipment_id,
            "status": self.status,
            "values": {key: self.values[key].to_dict() for key in sorted(self.values)},
            "constraints": {key: self.constraints[key].to_dict() for key in sorted(self.constraints)},
            "intermediates": _thaw(self.intermediates),
            "missing_inputs": list(self.missing_inputs),
            "conflicts": list(self.conflicts),
            "advisory": list(self.advisory),
            "validation_requests": list(self.validation_requests),
            "premise_event_ids": list(self.premise_event_ids),
            "derivations": [step.to_dict() for step in self.derivations],
        }

    @property
    def content_hash(self) -> str:
        return self.recompute_hash()

    def recompute_hash(self) -> str:
        return canonical_hash(self.semantic_dict())

    def to_dict(self) -> dict[str, Any]:
        return {**self.semantic_dict(), "content_hash": self.content_hash}

    def to_graph_proposal(self, run_id: str, base_version: str) -> GraphProposal:
        operations: list[GraphOperation] = []
        for view, node_type, decisions in (
            (View.PARAMETER_RULE, "ParameterValue", self.values),
            (View.GEOMETRY_SPATIAL, "Constraint", self.constraints),
        ):
            for name in sorted(decisions):
                decision = decisions[name]
                state = ValueState(decision.state)
                node = DesignNode.create(
                    view,
                    node_type,
                    f"{self.equipment_id}:{name}:{self.content_hash}",
                    {"name": name, **decision.to_dict()},
                    [],
                    state=state,
                )
                operations.append(GraphOperation("add_node", node.uid, node.to_dict()))
        return GraphProposal.create(
            run_id,
            base_version,
            (),
            tuple(operation.target for operation in operations),
            operations,
            self.premise_event_ids,
            ("schema", "units", "rules", "write_set"),
        )


class FoundationCalculator:
    REQUIRED_INPUTS = ("equipment_id", "dry_mass_kg", "installation_length_mm", "installation_width_mm")

    def __init__(self, package: CompiledRulePackage | None = None):
        self.package = package or load_default_package()

    def _rule_sources(self, rule_ids: Sequence[str]) -> tuple[str, ...]:
        return tuple(sorted({str(self.package.rule(rule_id)["source_locator"]) for rule_id in rule_ids}))

    def _decision(self, value: str | bool, unit: str, rule_ids: Sequence[str], state: str = "derived") -> ParameterDecision:
        ordered_rules = tuple(sorted(set(rule_ids)))
        return ParameterDecision(value, unit, state, ordered_rules, self._rule_sources(ordered_rules))

    def _external_mass(self, data: Mapping[str, Any]) -> tuple[Decimal | None, str, tuple[str, ...]]:
        loads = list(data.get("external_loads", ()))
        if not loads:
            scalar = Decimal(str(data.get("load_equivalent_mass_kg", "0")))
            return scalar, "specified" if scalar else "none", ()
        candidates: list[tuple[Decimal, str]] = []
        missing: list[str] = []
        for index, load in enumerate(loads):
            direction = str(load.get("direction", f"load-{index}"))
            if load.get("equivalent_mass_kg") is not None:
                candidates.append((Decimal(str(load["equivalent_mass_kg"])), direction))
                continue
            if load.get("force_N") is None:
                missing.append(f"external_loads[{index}].equivalent_mass_kg_or_force_N")
                continue
            if not load.get("authorize_force_conversion", False):
                missing.append(f"external_loads[{index}].authorize_force_conversion")
                continue
            if load.get("gravity_m_s2") is None:
                missing.append(f"external_loads[{index}].gravity_m_s2")
                continue
            mass = Quantity(load["force_N"], "N").equivalent_mass(Quantity(load["gravity_m_s2"], "m/s2"))
            candidates.append((mass.value, direction))
        if missing:
            return None, "unknown", tuple(sorted(missing))
        mass, direction = max(candidates, key=lambda item: (item[0], item[1]))
        return mass, direction, ()

    def calculate(self, data: Mapping[str, Any]) -> CalculationResult:
        missing = tuple(name for name in self.REQUIRED_INPUTS if data.get(name) is None)
        equipment_id = str(data.get("equipment_id", "unknown-equipment"))
        premises = tuple(sorted(set(data.get("premise_event_ids", ()))))
        if missing:
            return CalculationResult(equipment_id, "unknown", missing_inputs=missing, premise_event_ids=premises)

        length = Decimal(str(data["installation_length_mm"]))
        width = Decimal(str(data["installation_width_mm"]))
        if length <= 0 or width <= 0:
            return CalculationResult(equipment_id, "conflicted", conflicts=("installation_area",), premise_event_ids=premises)
        base_mass = sum(
            (Decimal(str(data.get(name, "0"))) for name in ("dry_mass_kg", "fluid_mass_kg", "attached_pipeline_mass_kg")),
            Decimal("0"),
        )
        external_mass, direction, load_missing = self._external_mass(data)
        if load_missing:
            return CalculationResult(equipment_id, "unknown", missing_inputs=load_missing, premise_event_ids=premises)
        total_mass = base_mass + (external_mass or Decimal("0"))
        area_m2 = length * width / Decimal("1000000")
        unit_area_mass = total_mass / area_m2
        thickness = thickness_for_load(
            unit_area_mass,
            moving=bool(data.get("moving_equipment")),
            in_plane_load=bool(data.get("in_plane_load")),
            package=self.package,
        )
        thickness_rules = tuple(sorted(thickness.rule_ids))
        values = {
            "panel_thickness_mm": self._decision(_decimal_text(thickness.panel_mm), "mm", thickness_rules),
            "web_bracket_thickness_mm": self._decision(_decimal_text(thickness.web_bracket_mm), "mm", thickness_rules),
        }
        constraints, conflicts, requests = self._geometry_constraints(data)
        status = "conflicted" if conflicts else "derived"
        intermediates = {
            "base_mass_kg": _decimal_text(base_mass),
            "selected_external_equivalent_mass_kg": _decimal_text(external_mass or Decimal("0")),
            "selected_total_mass_kg": _decimal_text(total_mass),
            "installation_area_m2": _decimal_text(area_m2),
            "unit_area_mass_kg_m2": _decimal_text(unit_area_mass),
            "governing_direction": direction,
            "base_or_adjusted_band_index": thickness.band_index,
        }
        derivations = (
            DerivationStep("mass", "sum_and_select_direction", ("dry_mass_kg", "external_loads"), "selected_total_mass_kg", ("formula.unit_area_mass.v1", "adjust.max_direction.v1")),
            DerivationStep("thickness", "decision_table", ("unit_area_mass_kg_m2",), "panel_thickness_mm", thickness_rules),
        )
        return CalculationResult(
            equipment_id,
            status,
            values,
            constraints,
            intermediates,
            conflicts=tuple(sorted(conflicts)),
            advisory=("material_selection_requires_engineering_review", "bracket_form_requires_engineering_review"),
            validation_requests=tuple(sorted(requests)),
            premise_event_ids=premises,
            derivations=derivations,
        )

    def _geometry_constraints(self, data: Mapping[str, Any]):
        constraints: dict[str, ParameterDecision] = {
            "bracket_spacing_min_mm": self._decision("200", "mm", ("geometry.bracket_spacing.v1",)),
        }
        conflicts: set[str] = set()
        requests: set[str] = set()
        diameter = Decimal(str(data["hole_diameter_mm"])) if data.get("hole_diameter_mm") is not None else None
        if diameter is None:
            requests.add("hole_geometry")
        else:
            constraints["hole_free_edge_min_mm"] = self._decision(_decimal_text(diameter * Decimal("2")), "mm", ("geometry.hole_free_edge.v1",))
            constraints["support_hole_distance_min_mm"] = self._decision(_decimal_text(diameter * Decimal("1.5")), "mm", ("geometry.support_hole_distance.v1",))
            constraints["support_hole_distance_max_mm"] = self._decision(_decimal_text(diameter * Decimal("3")), "mm", ("geometry.support_hole_distance.v1",))
            if data.get("system_type") == "propulsion":
                constraints["propulsion_member_distance_min_mm"] = self._decision(_decimal_text(diameter * Decimal("2")), "mm", ("geometry.propulsion_distance.v1",))
                constraints["propulsion_member_distance_max_mm"] = self._decision(_decimal_text(diameter * Decimal("2.5")), "mm", ("geometry.propulsion_distance.v1",))

        if data.get("web_height_mm") is None:
            requests.add("drainage_geometry")
        else:
            maximum = Decimal(str(data["web_height_mm"])) / Decimal("4")
            state = "conflicted" if maximum < Decimal("20") else "derived"
            constraints["drainage_hole_min_mm"] = self._decision("20", "mm", ("geometry.drainage_hole.v1",), state)
            constraints["drainage_hole_max_mm"] = self._decision(_decimal_text(maximum), "mm", ("geometry.drainage_hole.v1",), state)
            if state == "conflicted":
                conflicts.add("drainage_hole_range")

        cell = Decimal(str(data["cell_area_mm2"])) if data.get("cell_area_mm2") is not None else None
        opening = Decimal(str(data["opening_area_mm2"])) if data.get("opening_area_mm2") is not None else None
        plate = Decimal(str(data["plate_thickness_mm"])) if data.get("plate_thickness_mm") is not None else None
        if cell is None or opening is None or plate is None:
            requests.add("opening_geometry")
        if cell is not None:
            constraints["opening_area_max_mm2"] = self._decision(_decimal_text(cell * Decimal("0.5")), "mm2", ("geometry.opening_area.v1",))
        edge_flat_required = bool(cell and opening is not None and opening / cell > Decimal("0.333333333333333333"))
        if data.get("opening_radius_mm") is not None and Decimal(str(data["opening_radius_mm"])) > Decimal("200"):
            edge_flat_required = True
        if cell is not None or data.get("opening_radius_mm") is not None:
            rule_ids = ["geometry.opening_area.v1"]
            if data.get("opening_radius_mm") is not None:
                rule_ids.append("geometry.opening_radius.v1")
            constraints["edge_flat_bar_required"] = self._decision(edge_flat_required, "boolean", rule_ids)
        if plate is not None:
            constraints["opening_edge_distance_min_mm"] = self._decision(_decimal_text(plate * Decimal("20")), "mm", ("geometry.opening_edge.v1",))
            constraints["direct_opening_max_size_mm"] = self._decision(_decimal_text(plate * Decimal("10")), "mm", ("geometry.direct_opening.v1",))
            constraints["direct_opening_clearance_min_exclusive_mm"] = self._decision(_decimal_text(plate * Decimal("20")), "mm", ("geometry.direct_opening.v1",))

        if data.get("penetration_height_mm") is None or data.get("member_height_mm") is None:
            requests.add("penetration_geometry")
        else:
            ratio = Decimal(str(data["penetration_height_mm"])) / Decimal(str(data["member_height_mm"]))
            constraints["doubler_required"] = self._decision(ratio > Decimal("0.5"), "boolean", ("geometry.penetration_doubler.v1",))
        return constraints, conflicts, requests
