from gencore.orchestration import AgentOutcome, AgentRole, default_role_policies
from gencore.ports import (
    ApprovalDecision,
    InMemoryApprovalGateway,
    RegistryToolExecutor,
    ScriptedAgentRuntime,
    ScriptedToolExecutor,
    ToolRequest,
)
from gencore.tool_registry import ToolRegistry, ToolSpec


def test_scripted_runtime_replays_outcomes_without_framework_dependency():
    runtime = ScriptedAgentRuntime(
        {"task:scene": AgentOutcome(status="completed", evidence_refs=("evt:1",))}
    )

    result = runtime.invoke(
        {"task_id": "task:scene"},
        {"graph_version": "ver:1"},
    )

    assert result.evidence_refs == ("evt:1",)
    assert runtime.calls == [("task:scene", "ver:1")]


def test_scripted_tool_executor_returns_declared_result():
    executor = ScriptedToolExecutor(
        {
            "foundation.parameters.calculate": {
                "status": "completed",
                "result": {"panel_thickness_mm": "8"},
            }
        }
    )

    outcome = executor.execute(
        AgentRole.SOLUTION_PARAMETER,
        ToolRequest("foundation.parameters.calculate", {"dry_mass_kg": "900"}),
    )

    assert outcome.status == "completed"
    assert outcome.result["panel_thickness_mm"] == "8"


def test_registry_executor_enforces_role_tool_whitelist():
    registry = ToolRegistry(
        [
            ToolSpec(
                "foundation.parameters.calculate",
                "calculate",
                {"type": "object"},
                {"type": "object"},
                "read_only",
                "offline",
                lambda payload: {"echo": payload},
            )
        ]
    )
    executor = RegistryToolExecutor(
        registry,
        default_role_policies(),
        InMemoryApprovalGateway(),
    )

    outcome = executor.execute(
        AgentRole.VALIDATION,
        ToolRequest("foundation.parameters.calculate", {}),
    )

    assert outcome.status == "permission_denied"
    assert outcome.result == {}


def test_external_tool_requires_recorded_approval():
    registry = ToolRegistry(
        [
            ToolSpec(
                "geometry.cad.update_parameters",
                "update",
                {"type": "object"},
                {"type": "object"},
                "external_cad",
                "optional_backend",
                lambda payload: {"executed": payload["allow_external_cad"]},
            )
        ]
    )
    denied = RegistryToolExecutor(
        registry,
        default_role_policies(),
        InMemoryApprovalGateway(),
    ).execute(
        AgentRole.CAD_EXECUTOR,
        ToolRequest(
            "geometry.cad.update_parameters",
            {},
            operation_id="op:1",
            graph_version="ver:1",
        ),
    )
    approvals = InMemoryApprovalGateway(
        {
            "op:1": ApprovalDecision(
                approved=True,
                mode="approve_once",
                event_id="evt:" + "a" * 64,
            )
        }
    )
    approved = RegistryToolExecutor(
        registry,
        default_role_policies(),
        approvals,
    ).execute(
        AgentRole.CAD_EXECUTOR,
        ToolRequest(
            "geometry.cad.update_parameters",
            {},
            operation_id="op:1",
            graph_version="ver:1",
        ),
    )

    assert denied.status == "approval_required"
    assert approved.status == "completed"
    assert approved.result == {"executed": True}
    assert approved.approval_event_id == "evt:" + "a" * 64
