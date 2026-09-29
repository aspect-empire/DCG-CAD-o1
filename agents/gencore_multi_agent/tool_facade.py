"""Role-filtered LangChain tool facade over the deterministic registry."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from gencore.orchestration.roles import AgentRole, default_role_policies
from gencore.tool_registry import ToolRegistry, build_default_registry


class ToolFacade:
    def __init__(
        self,
        *,
        workspace_root: str | Path,
        allow_external_cad: bool,
        registry: ToolRegistry | None = None,
    ) -> None:
        self.workspace_root = Path(workspace_root).absolute()
        self.allow_external_cad = allow_external_cad
        self.registry = registry or build_default_registry(
            workspace_root=self.workspace_root
        )
        self.policies = default_role_policies()
        self.metadata = {
            item["name"]: item for item in self.registry.list_tools()
        }

    def tools_for(self, role: AgentRole) -> list[Any]:
        names = sorted(self.policies[AgentRole(role)].tool_names)
        return [
            self._tool(name)
            for name in names
            if name in self.metadata
            and (
                self.metadata[name]["risk_level"] != "external_cad"
                or self.allow_external_cad
            )
        ]

    def root_tools(self) -> list[Any]:
        names = set(self.policies[AgentRole.COORDINATOR].tool_names)
        if self.allow_external_cad:
            names.update(
                name
                for name, value in self.metadata.items()
                if value["risk_level"] == "external_cad"
            )
        return [self._tool(name) for name in sorted(names) if name in self.metadata]

    def external_tool_names(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                name
                for name, value in self.metadata.items()
                if value["risk_level"] == "external_cad"
            )
        )

    def invoke(self, name: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Invoke safe tools or declare an approval-gated external CAD request."""

        metadata = self.metadata[name]
        value = dict(payload)
        value["workspace_root"] = str(self.workspace_root)
        if metadata["risk_level"] != "external_cad":
            return self.registry.invoke(name, value)
        if not self.allow_external_cad:
            raise PermissionError("external CAD is disabled")
        required = ("run_id", "operation_id", "graph_version")
        missing = [field for field in required if not value.get(field)]
        if missing:
            raise ValueError(
                "external CAD declaration requires: " + ", ".join(missing)
            )
        value.pop("workspace_root", None)
        return {
            "status": "approval_required",
            "requires_gateway_approval": True,
            "tool_request": {
                "name": name,
                "operation_id": str(value.pop("operation_id")),
                "graph_version": str(value.get("graph_version")),
                "payload": value,
            },
        }

    def _tool(self, name: str) -> Any:
        try:
            from langchain_core.tools import StructuredTool
        except ImportError as exc:
            raise RuntimeError(
                "The DeepAgent adapter requires the optional 'agent' dependencies."
            ) from exc

        metadata = self.metadata[name]

        def invoke(payload: dict[str, Any]) -> dict[str, Any]:
            """Invoke one role-approved GenCore tool with a JSON object payload."""
            return self.invoke(name, payload)

        return StructuredTool.from_function(
            func=invoke,
            name=name,
            description=str(metadata["description"]),
        )


__all__ = ["ToolFacade"]
