from types import SimpleNamespace

import pytest

from gencore.orchestration import AgentOutcome, DesignExecutionPackage, Stage
from gencore.orchestration.coordinator import Coordinator
from gencore.orchestration.decision import DecisionEvaluator
from gencore.orchestration.evidence_router import EvidenceRouter
from gencore.orchestration.roles import default_role_policies
from gencore.orchestration.state_repository import WorkspaceStateRepository
from gencore.orchestration.task_graph import DefaultTaskBuilder
from gencore.orchestration.transaction_gateway import TransactionGateway
from gencore.ports import (
    AllowReadOnlyApproval,
    ScriptedAgentRuntime,
    ScriptedToolExecutor,
)


@pytest.fixture
def scripted_ports(tmp_path):
    repository = WorkspaceStateRepository(tmp_path, run_id="run-1")
    genesis = repository.head.version_id
    package = DesignExecutionPackage.create(
        task_id="GEN-001",
        scenario_id="SCN-01",
        run_id="run-1",
        graph_version=genesis,
        stage=Stage.S0_INITIALIZE,
        design_intent={"object": "框架式基座"},
        unknown_constraints=({"constraint_id": "scene", "critical": True},),
    )
    repository.save_package(package)
    agent_runtime = ScriptedAgentRuntime(
        {
            "task:scene": AgentOutcome(
                status="completed", evidence_refs=("evt:scene",)
            ),
            "task:validate": AgentOutcome(status="completed", evidence_refs=()),
        }
    )
    policies = default_role_policies()
    coordinator = Coordinator(
        repository=repository,
        agent_runtime=agent_runtime,
        role_policies=policies,
        task_builder=DefaultTaskBuilder(),
        transaction_gateway=TransactionGateway(repository, policies),
        tool_executor=ScriptedToolExecutor({}),
        approval_gateway=AllowReadOnlyApproval(),
        evidence_router=EvidenceRouter.default(),
        decision_evaluator=DecisionEvaluator(),
    )
    return SimpleNamespace(
        coordinator=coordinator,
        agent_runtime=agent_runtime,
        repository=repository,
        genesis=genesis,
    )
