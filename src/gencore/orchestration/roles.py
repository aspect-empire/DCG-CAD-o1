"""Code-enforced graph and tool boundaries for specialist roles."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path
from typing import Any, Mapping


class AgentRole(str, Enum):
    COORDINATOR = "coordinator"
    SCENE_CONSTRAINT = "scene_constraint"
    SOLUTION_PARAMETER = "solution_parameter"
    GEOMETRY_PLANNING = "geometry_planning"
    CAD_EXECUTOR = "cad_executor"
    VALIDATION = "validation"
    REPAIR_REFLECTION = "repair_reflection"
    EXPERT = "expert"


@dataclass(frozen=True)
class RolePolicy:
    readable_views: frozenset[str]
    writable_node_types: frozenset[str]
    writable_operation_kinds: frozenset[str]
    tool_names: frozenset[str]
    model_enabled: bool

    def __post_init__(self) -> None:
        groups = (
            self.readable_views,
            self.writable_node_types,
            self.writable_operation_kinds,
            self.tool_names,
        )
        if any("*" in group for group in groups):
            raise ValueError("wildcard role permissions are prohibited")
        if not self.readable_views:
            raise ValueError("every role requires at least one readable graph view")

    def allows_tool(self, name: str) -> bool:
        return name in self.tool_names

    def allows_node_write(self, node_type: str) -> bool:
        return node_type in self.writable_node_types

    def allows_operation(self, kind: str) -> bool:
        return kind in self.writable_operation_kinds


def _config_root() -> Path:
    return Path(__file__).resolve().parents[3] / "config" / "orchestration"


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("version") != 1:
        raise ValueError(f"{path.name} requires version 1")
    return value


def default_role_policies(
    *,
    roles_path: str | Path | None = None,
    tools_path: str | Path | None = None,
) -> dict[AgentRole, RolePolicy]:
    root = _config_root()
    role_config = _load_json(Path(roles_path) if roles_path else root / "roles.json")
    tool_config = _load_json(
        Path(tools_path) if tools_path else root / "tool_permissions.json"
    )
    declared_roles = set(role_config.get("roles", {}))
    tool_roles = set(tool_config.get("roles", {}))
    expected = {role.value for role in AgentRole}
    if declared_roles != expected or tool_roles != expected:
        raise ValueError("role and tool configurations must cover every AgentRole exactly")

    policies: dict[AgentRole, RolePolicy] = {}
    for role in AgentRole:
        raw = role_config["roles"][role.value]
        tools = tool_config["roles"][role.value]
        policies[role] = RolePolicy(
            readable_views=frozenset(str(value) for value in raw["readable_views"]),
            writable_node_types=frozenset(
                str(value) for value in raw["writable_node_types"]
            ),
            writable_operation_kinds=frozenset(
                str(value) for value in raw["writable_operation_kinds"]
            ),
            tool_names=frozenset(str(value) for value in tools),
            model_enabled=bool(raw["model_enabled"]),
        )
    return policies


def project_view(snapshot: Mapping[str, Any], policy: RolePolicy) -> dict[str, Any]:
    nodes = {
        str(uid): dict(record)
        for uid, record in snapshot.get("nodes", {}).items()
        if record.get("view") in policy.readable_views
    }
    visible = set(nodes)
    edges = {
        str(uid): dict(record)
        for uid, record in snapshot.get("edges", {}).items()
        if record.get("source") in visible and record.get("target") in visible
    }
    return {"nodes": nodes, "edges": edges}


__all__ = [
    "AgentRole",
    "RolePolicy",
    "default_role_policies",
    "project_view",
]
