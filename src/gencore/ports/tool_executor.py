"""Tool execution port with role and approval enforcement."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping, Protocol

from gencore.orchestration.roles import AgentRole, RolePolicy
from gencore.tool_registry import ToolRegistry

from .approval import ApprovalGateway, ApprovalRequest


@dataclass(frozen=True)
class ToolRequest:
    name: str
    payload: Mapping[str, Any]
    operation_id: str | None = None
    graph_version: str | None = None

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("tool request name must be non-empty")
        object.__setattr__(self, "payload", MappingProxyType(dict(self.payload)))


@dataclass(frozen=True)
class ToolOutcome:
    name: str
    status: str
    result: Mapping[str, Any] = field(default_factory=dict)
    error: Mapping[str, Any] | None = None
    approval_event_id: str | None = None


class ToolExecutor(Protocol):
    def execute(self, role: AgentRole, request: ToolRequest) -> ToolOutcome: ...


class ScriptedToolExecutor:
    def __init__(self, outcomes: Mapping[str, Mapping[str, Any]]) -> None:
        self.outcomes = {name: dict(value) for name, value in outcomes.items()}
        self.calls: list[tuple[AgentRole, ToolRequest]] = []

    def execute(self, role: AgentRole, request: ToolRequest) -> ToolOutcome:
        role = AgentRole(role)
        self.calls.append((role, request))
        try:
            raw = self.outcomes[request.name]
        except KeyError as exc:
            raise KeyError(f"no scripted tool outcome for: {request.name}") from exc
        return ToolOutcome(
            request.name,
            str(raw.get("status", "completed")),
            MappingProxyType(dict(raw.get("result", {}))),
            raw.get("error"),
            raw.get("approval_event_id"),
        )


class RegistryToolExecutor:
    def __init__(
        self,
        registry: ToolRegistry,
        role_policies: Mapping[AgentRole, RolePolicy],
        approval_gateway: ApprovalGateway,
    ) -> None:
        self.registry = registry
        self.role_policies = dict(role_policies)
        self.approval_gateway = approval_gateway

    def execute(self, role: AgentRole, request: ToolRequest) -> ToolOutcome:
        role = AgentRole(role)
        policy = self.role_policies[role]
        if not policy.allows_tool(request.name):
            return ToolOutcome(
                request.name,
                "permission_denied",
                error=MappingProxyType(
                    {
                        "type": "PermissionError",
                        "message": f"{role.value} cannot invoke {request.name}",
                    }
                ),
            )
        metadata = {item["name"]: item for item in self.registry.list_tools()}
        if request.name not in metadata:
            return ToolOutcome(
                request.name,
                "unknown_tool",
                error=MappingProxyType(
                    {"type": "KeyError", "message": f"unknown tool: {request.name}"}
                ),
            )

        payload = dict(request.payload)
        approval_event_id = None
        if metadata[request.name]["risk_level"] == "external_cad":
            if not request.operation_id or not request.graph_version:
                return ToolOutcome(
                    request.name,
                    "approval_required",
                    error=MappingProxyType(
                        {
                            "type": "ApprovalRequired",
                            "message": "operation_id and graph_version are required",
                        }
                    ),
                )
            decision = self.approval_gateway.request(
                ApprovalRequest(
                    request.operation_id,
                    request.name,
                    request.graph_version,
                    "external_cad",
                    str(payload.get("run_id", "")) or None,
                )
            )
            if not decision.approved:
                return ToolOutcome(
                    request.name,
                    "approval_required",
                    error=MappingProxyType(
                        {
                            "type": "ApprovalRequired",
                            "message": decision.reason or "external CAD approval was denied",
                        }
                    ),
                )
            payload["allow_external_cad"] = True
            approval_event_id = decision.event_id

        try:
            result = self.registry.invoke(request.name, payload)
        except Exception as exc:
            return ToolOutcome(
                request.name,
                "failed",
                error=MappingProxyType(
                    {"type": type(exc).__name__, "message": str(exc)}
                ),
                approval_event_id=approval_event_id,
            )
        return ToolOutcome(
            request.name,
            "completed",
            MappingProxyType(dict(result)),
            approval_event_id=approval_event_id,
        )


__all__ = [
    "RegistryToolExecutor",
    "ScriptedToolExecutor",
    "ToolExecutor",
    "ToolOutcome",
    "ToolRequest",
]
