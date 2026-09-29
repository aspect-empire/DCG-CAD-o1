"""Traceable deterministic graph reasoning rules."""

from __future__ import annotations

from collections import defaultdict, deque
from decimal import Decimal, InvalidOperation
from typing import Any

from .graph import EngineeringGraph


class GraphReasoner:
    FUSION_RULE = "parameter_evidence_fusion/v1"
    FAILURE_CODES = {
        "BOOLEAN_FAILED": "cad.boolean_operation_failed",
        "EDGE_TOO_SMALL": "validation.edge_clearance_failed",
        "VALIDATION_FAILED": "validation.failed",
    }

    def __init__(self, engineering_graph: EngineeringGraph):
        self.engineering_graph = engineering_graph
        self.graph = engineering_graph.graph

    @staticmethod
    def _canonical_value(value: Any, unit: Any) -> tuple[Any, str]:
        """Normalize common engineering length units and numeric strings."""
        raw_unit = str(unit or "").strip().lower()
        unit_aliases = {
            "mm": ("mm", Decimal("1")),
            "millimeter": ("mm", Decimal("1")),
            "millimetre": ("mm", Decimal("1")),
            "cm": ("mm", Decimal("10")),
            "m": ("mm", Decimal("1000")),
        }
        canonical_unit, multiplier = unit_aliases.get(raw_unit, (raw_unit, Decimal("1")))
        try:
            numeric = Decimal(str(value)) * multiplier
        except (InvalidOperation, ValueError):
            return value, canonical_unit
        return numeric.normalize(), canonical_unit

    @staticmethod
    def _json_value(value: Any) -> Any:
        if isinstance(value, Decimal):
            return int(value) if value == value.to_integral_value() else float(value)
        return value

    def fuse_parameters(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for parameter_uid, data in sorted(self.graph.nodes(data=True)):
            if data.get("node_type") != "Parameter":
                continue
            observations = list(data.get("observations", ()))
            grouped: dict[tuple[Any, str], list[str]] = defaultdict(list)
            for item in observations:
                grouped[self._canonical_value(item.get("value"), item.get("unit", ""))].append(item["event_id"])
            premises = sorted({item["event_id"] for item in observations})
            if len(grouped) == 1 and observations:
                (value, unit), _ = next(iter(grouped.items()))
                if isinstance(value, Decimal):
                    value = int(value) if value == value.to_integral_value() else float(value)
                status = "fused" if len(premises) > 1 else "single_source"
            else:
                value = unit = None
                status = "conflict" if grouped else "no_evidence"
            result = {"parameter_uid": parameter_uid, "parameter": data.get("name"), "value": value,
                      "unit": unit, "status": status, "premise_event_ids": premises,
                      "alternatives": [{"value": self._json_value(key[0]), "unit": key[1], "event_ids": sorted(ids)}
                                       for key, ids in sorted(grouped.items(), key=lambda item: repr(item[0]))]}
            results.append(result)
            if len(premises) > 1 and status == "fused":
                evidence_nodes = [uid for uid, attrs in self.graph.nodes(data=True)
                                  if attrs.get("node_type") == "Evidence" and attrs.get("event_id") in premises]
                for evidence in sorted(evidence_nodes):
                    self.engineering_graph.add_edge(evidence, parameter_uid, "BASED_ON", origin="derived",
                                                    premise_event_ids=premises, derived_by=self.FUSION_RULE,
                                                    discriminator=[self.FUSION_RULE, evidence, premises])
        return results

    @classmethod
    def normalize_failure(cls, failure: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(failure)
        code = str(failure.get("raw_error_code") or failure.get("code") or "UNKNOWN")
        normalized["raw_error_code"] = code
        normalized["signature"] = cls.FAILURE_CODES.get(code.upper(), f"unclassified.{code.lower()}")
        normalized.setdefault("status", "failed")
        return normalized

    def affected_subgraph(self, start_uid: str, *, max_depth: int | None = None) -> set[str]:
        if start_uid not in self.graph:
            return set()
        start_is_task = self.graph.nodes[start_uid].get("node_type") == "Task"
        start_is_parameter = self.graph.nodes[start_uid].get("node_type") == "Parameter"
        visited = {start_uid}
        queue = deque([(start_uid, 0)])
        while queue:
            uid, depth = queue.popleft()
            if max_depth is not None and depth >= max_depth:
                continue
            neighbours: set[str] = set()
            for _, neighbour, _, edge in self.graph.out_edges(uid, keys=True, data=True):
                if edge.get("active", True):
                    neighbours.add(neighbour)
            for neighbour, _, _, edge in self.graph.in_edges(uid, keys=True, data=True):
                if edge.get("active", True):
                    neighbours.add(neighbour)
            for neighbour in sorted(neighbours):
                if not self.graph.nodes[neighbour].get("active", True):
                    continue
                if not start_is_task and self.graph.nodes[neighbour].get("node_type") == "Task":
                    continue
                if start_is_parameter and neighbour != start_uid and self.graph.nodes[neighbour].get("node_type") == "Parameter":
                    continue
                if neighbour not in visited:
                    visited.add(neighbour)
                    queue.append((neighbour, depth + 1))
        return visited


Reasoner = GraphReasoner
