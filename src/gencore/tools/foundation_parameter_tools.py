"""Shared deterministic entry point for foundation parameter calculation."""

from __future__ import annotations

from typing import Any, Mapping

from gencore.foundation_rules import FoundationCalculator
from gencore.tool_registry import ToolSpec


OBJECT_SCHEMA = {"type": "object"}


def calculate_foundation_parameters(payload: Mapping[str, Any]) -> dict[str, Any]:
    for required in ("run_id", "base_version"):
        if not payload.get(required):
            raise ValueError(f"{required} is required")
    result = FoundationCalculator().calculate(payload)
    output = result.to_dict()
    output["graph_proposal"] = result.to_graph_proposal(
        str(payload["run_id"]),
        str(payload["base_version"]),
    ).to_dict()
    return output


def foundation_parameter_tool_specs() -> list[ToolSpec]:
    return [
        ToolSpec(
            "foundation.parameters.calculate",
            "Calculate traceable foundation parameters from the frozen rule package.",
            OBJECT_SCHEMA,
            OBJECT_SCHEMA,
            "read_only",
            "offline",
            lambda payload: calculate_foundation_parameters(payload),
        )
    ]


__all__ = [
    "calculate_foundation_parameters",
    "foundation_parameter_tool_specs",
]
