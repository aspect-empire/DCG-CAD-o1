"""Normalized registry for deterministic GenCore tools."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Callable, Iterable, Literal


RiskLevel = Literal["read_only", "workspace_write", "external_cad"]
ExecutionMode = Literal["offline", "optional_backend"]
ToolHandler = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    risk_level: RiskLevel
    execution_mode: ExecutionMode
    handler: ToolHandler

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("tool name must be a non-empty string")
        if self.risk_level not in {"read_only", "workspace_write", "external_cad"}:
            raise ValueError(f"invalid risk_level: {self.risk_level}")
        if self.execution_mode not in {"offline", "optional_backend"}:
            raise ValueError(f"invalid execution_mode: {self.execution_mode}")
        if not isinstance(self.input_schema, dict) or not isinstance(self.output_schema, dict):
            raise TypeError("tool schemas must be dicts")
        if not callable(self.handler):
            raise TypeError("tool handler must be callable")

    def metadata(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "risk_level": self.risk_level,
            "execution_mode": self.execution_mode,
        }


class ToolRegistry:
    def __init__(self, specs: Iterable[ToolSpec] = ()) -> None:
        self._tools: dict[str, ToolSpec] = {}
        for spec in specs:
            self.register(spec)

    def register(self, spec: ToolSpec) -> None:
        if spec.name in self._tools:
            raise ValueError(f"duplicate tool name: {spec.name}")
        json.dumps(spec.metadata(), ensure_ascii=False, allow_nan=False)
        self._tools[spec.name] = spec

    def list_tools(self) -> list[dict[str, Any]]:
        return [self._tools[name].metadata() for name in sorted(self._tools)]

    def invoke(self, name: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise TypeError("tool input must be a dict")
        try:
            spec = self._tools[name]
        except KeyError as exc:
            raise KeyError(f"unknown tool: {name}") from exc
        if spec.risk_level == "external_cad" and payload.get("allow_external_cad") is not True:
            raise PermissionError("external CAD tools require allow_external_cad=true")
        result = spec.handler(dict(payload))
        if not isinstance(result, dict):
            raise TypeError("tool output must be a dict")
        try:
            json.dumps(result, ensure_ascii=False, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise ValueError("tool output must be JSON-serializable") from exc
        return result


def build_default_registry(*, workspace_root: str | Path | None = None) -> ToolRegistry:
    from .tools import all_tool_specs

    return ToolRegistry(all_tool_specs(workspace_root=workspace_root))


__all__ = ["ExecutionMode", "RiskLevel", "ToolRegistry", "ToolSpec", "build_default_registry"]
