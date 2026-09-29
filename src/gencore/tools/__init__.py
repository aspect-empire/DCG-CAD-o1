"""Built-in normalized GenCore tool specifications."""

from __future__ import annotations

from pathlib import Path

from ..tool_registry import ToolSpec
from .case_matching_tools import case_matching_tool_specs
from .foundation_parameter_tools import foundation_parameter_tool_specs
from .graph_tools import graph_tool_specs
from .orchestration_tools import orchestration_tool_specs


def all_tool_specs(*, workspace_root: str | Path | None = None) -> list[ToolSpec]:
    return [
        *case_matching_tool_specs(),
        *foundation_parameter_tool_specs(),
        *orchestration_tool_specs(workspace_root=workspace_root),
        *graph_tool_specs(workspace_root=workspace_root),
    ]


__all__ = [
    "all_tool_specs",
    "case_matching_tool_specs",
    "foundation_parameter_tool_specs",
    "graph_tool_specs",
    "orchestration_tool_specs",
]
