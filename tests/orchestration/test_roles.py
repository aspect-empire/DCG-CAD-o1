import json
from pathlib import Path

import pytest

from gencore.orchestration.roles import (
    AgentRole,
    RolePolicy,
    default_role_policies,
    project_view,
)


def test_parameter_agent_cannot_call_catia_or_write_validation():
    policy = default_role_policies()[AgentRole.SOLUTION_PARAMETER]

    assert policy.allows_tool("foundation.case_matching.match")
    assert policy.allows_tool("foundation.parameters.calculate")
    assert not policy.allows_tool("geometry.cad.update_parameters")
    assert not policy.allows_node_write("Validation")


def test_validation_agent_can_write_evidence_but_not_parameters():
    policy = default_role_policies()[AgentRole.VALIDATION]

    assert policy.allows_node_write("Evidence")
    assert policy.allows_node_write("Validation")
    assert not policy.allows_node_write("ParameterValue")


def test_cad_executor_is_deterministic_and_cannot_write_constraints():
    policy = default_role_policies()[AgentRole.CAD_EXECUTOR]

    assert policy.model_enabled is False
    assert policy.allows_node_write("Artifact")
    assert policy.allows_node_write("GeometryReference")
    assert not policy.allows_node_write("Constraint")


def test_project_view_filters_nodes_and_dangling_edges():
    policy = RolePolicy(
        readable_views=frozenset({"parameter_rule"}),
        writable_node_types=frozenset(),
        writable_operation_kinds=frozenset(),
        tool_names=frozenset(),
        model_enabled=True,
    )
    snapshot = {
        "nodes": {
            "node:p": {"uid": "node:p", "view": "parameter_rule"},
            "node:g": {"uid": "node:g", "view": "geometry_spatial"},
        },
        "edges": {
            "edge:pp": {"uid": "edge:pp", "source": "node:p", "target": "node:p"},
            "edge:pg": {"uid": "edge:pg", "source": "node:p", "target": "node:g"},
        },
    }

    projected = project_view(snapshot, policy)

    assert set(projected["nodes"]) == {"node:p"}
    assert set(projected["edges"]) == {"edge:pp"}


def test_role_configuration_has_no_wildcards_and_covers_all_roles():
    config = json.loads(
        Path("config/orchestration/roles.json").read_text(encoding="utf-8")
    )

    assert set(config["roles"]) == {role.value for role in AgentRole}
    assert "*" not in json.dumps(config)


def test_role_policy_rejects_wildcards():
    with pytest.raises(ValueError, match="wildcard"):
        RolePolicy(
            readable_views=frozenset({"*"}),
            writable_node_types=frozenset(),
            writable_operation_kinds=frozenset(),
            tool_names=frozenset(),
            model_enabled=True,
        )
