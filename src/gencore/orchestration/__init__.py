"""Framework-neutral orchestration contracts and services."""

from typing import TYPE_CHECKING

from .contracts import AgentOutcome, DesignDecision, DesignExecutionPackage, Stage
from .coordinator import Coordinator, StepResult
from .decision import DecisionEvaluator, DecisionResult
from .mechanisms import MechanismControls
from .repair import RepairAction, RepairPlan, RepairPlanner, RepairPolicy
from .roles import AgentRole, RolePolicy, default_role_policies, project_view
from .state_machine import StageMachine
from .state_repository import WorkspaceStateRepository
from .task_graph import DefaultTaskBuilder, DesignTask, TaskGraph, TaskStatus
from .transaction_gateway import TransactionGateway, TransactionResult

if TYPE_CHECKING:
    from .runtime import DesignRuntime, RuntimeResult


def __getattr__(name: str):
    if name in {"DesignRuntime", "RuntimeResult", "replay_fixture"}:
        from . import runtime

        return getattr(runtime, name)
    raise AttributeError(name)

__all__ = [
    "AgentOutcome",
    "AgentRole",
    "Coordinator",
    "DefaultTaskBuilder",
    "DesignRuntime",
    "DesignDecision",
    "DesignExecutionPackage",
    "DecisionEvaluator",
    "DecisionResult",
    "MechanismControls",
    "RepairAction",
    "RepairPlan",
    "RepairPlanner",
    "RepairPolicy",
    "RuntimeResult",
    "StepResult",
    "DesignTask",
    "RolePolicy",
    "Stage",
    "StageMachine",
    "TaskGraph",
    "TaskStatus",
    "TransactionGateway",
    "TransactionResult",
    "WorkspaceStateRepository",
    "default_role_policies",
    "project_view",
    "replay_fixture",
]
