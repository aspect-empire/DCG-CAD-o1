"""One-ready-task-per-step portable design coordinator."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from gencore.design_state import GraphProposal
from gencore.ports import ToolRequest

from .contracts import DesignDecision, DesignExecutionPackage
from .mechanisms import MechanismControls
from .roles import AgentRole, RolePolicy, project_view


@dataclass(frozen=True)
class StepResult:
    dispatched_task_id: str | None
    graph_version: str
    decision: DesignDecision
    tool_results: tuple[Any, ...]
    transaction_results: tuple[Any, ...]


class Coordinator:
    def __init__(
        self,
        *,
        repository: Any,
        agent_runtime: Any,
        role_policies: Mapping[AgentRole, RolePolicy],
        task_builder: Any,
        transaction_gateway: Any,
        tool_executor: Any,
        approval_gateway: Any,
        evidence_router: Any,
        decision_evaluator: Any,
        mechanism_controls: MechanismControls | None = None,
    ) -> None:
        self.repository = repository
        self.agent_runtime = agent_runtime
        self.role_policies = dict(role_policies)
        self.task_builder = task_builder
        self.transaction_gateway = transaction_gateway
        self.tool_executor = tool_executor
        self.approval_gateway = approval_gateway
        self.evidence_router = evidence_router
        self.decision_evaluator = decision_evaluator
        self.mechanism_controls = mechanism_controls or MechanismControls()

    def step(self, run_id: str) -> StepResult:
        package = self.repository.load_current_package(run_id)
        snapshot = self.repository.read_snapshot(package.graph_version)
        ready = self.task_builder.build(package, snapshot).ready()
        if not ready:
            decision = self.decision_evaluator.evaluate(snapshot)
            self._save_package(package, None, decision.decision)
            return StepResult(None, self.repository.head.version_id, decision.decision, (), ())

        task = (
            ready[0]
            if self.mechanism_controls.fixed_stage_order
            else min(ready, key=lambda item: item.task_id)
        )
        if (
            task.role is AgentRole.REPAIR_REFLECTION
            and not self.mechanism_controls.local_repair
        ):
            self._save_package(package, None, DesignDecision.ABSTAINED)
            return StepResult(
                None,
                self.repository.head.version_id,
                DesignDecision.ABSTAINED,
                (),
                (),
            )
        role_view = project_view(snapshot, self.role_policies[task.role])
        context = {
            "graph_version": package.graph_version,
            "state_view": self.mechanism_controls.project_state(role_view),
            "execution_package": package.to_dict(),
            "allowed_tools": sorted(self.role_policies[task.role].tool_names),
            "coordination_mode": (
                "multi_agent"
                if self.mechanism_controls.multi_agent
                else "single_agent"
            ),
            "fixed_stage_order": self.mechanism_controls.fixed_stage_order,
            "failure_strategy": self.mechanism_controls.failure_strategy,
        }
        outcome = self.agent_runtime.invoke(task.to_dict(), context)
        transaction_results = []
        tool_results = []
        for proposal in outcome.graph_proposals:
            if not self.mechanism_controls.allows_graph_writeback(
                task.role.value
            ):
                continue
            transaction_results.append(
                self.transaction_gateway.submit(
                    task.role, GraphProposal.from_dict(proposal)
                )
            )
        for raw_request in outcome.tool_requests:
            request = self._tool_request(raw_request, package.graph_version)
            tool_result = self.tool_executor.execute(task.role, request)
            tool_results.append(tool_result)
            if not self.mechanism_controls.allows_graph_writeback(
                task.role.value
            ):
                continue
            routed = self.evidence_router.to_proposal(
                request=request,
                outcome=tool_result,
                base_version=self.repository.head.version_id,
            )
            transaction_results.append(
                self.transaction_gateway.submit(routed.role, routed.proposal)
            )

        current_snapshot = self.repository.read_snapshot()
        task_status = outcome.status
        if any(self._tool_failed(item) for item in tool_results):
            task_status = "failed"
        next_package = self._save_package(
            package,
            {
                "task_id": task.task_id,
                "status": task_status,
                "role": task.role.value,
                "evidence_refs": (
                    list(outcome.evidence_refs)
                    if self.mechanism_controls.provenance_tracking
                    else []
                ),
                "graph_version": self.repository.head.version_id,
            },
            DesignDecision.RUNNING,
        )
        requested_terminal = (
            outcome.requested_decision
            if task.role is AgentRole.VALIDATION
            and outcome.requested_decision
            in {
                DesignDecision.HUMAN_REQUIRED,
                DesignDecision.REJECTED,
                DesignDecision.ABSTAINED,
            }
            else None
        )
        remaining = self.task_builder.build(next_package, current_snapshot).ready()
        decision = requested_terminal or (
            DesignDecision.RUNNING
            if remaining
            else self.decision_evaluator.evaluate(current_snapshot).decision
        )
        if decision is not DesignDecision.RUNNING:
            self._save_package(next_package, None, decision)
        return StepResult(
            task.task_id,
            self.repository.head.version_id,
            decision,
            tuple(tool_results),
            tuple(transaction_results),
        )

    @staticmethod
    def _tool_failed(outcome: Any) -> bool:
        if str(outcome.status) not in {"completed", "success", "passed"}:
            return True
        nested_status = str((outcome.result or {}).get("status", "completed"))
        return nested_status not in {"completed", "success", "passed"}

    @staticmethod
    def _tool_request(value: Mapping[str, Any], graph_version: str) -> ToolRequest:
        return ToolRequest(
            name=str(value["name"]),
            payload=dict(value.get("payload", {})),
            operation_id=(
                str(value["operation_id"]) if value.get("operation_id") is not None else None
            ),
            graph_version=str(value.get("graph_version") or graph_version),
        )

    def _save_package(
        self,
        package: DesignExecutionPackage,
        provenance: Mapping[str, Any] | None,
        decision: DesignDecision,
    ) -> DesignExecutionPackage:
        value = package.to_dict()
        value.pop("package_id")
        value["graph_version"] = self.repository.head.version_id
        value["current_decision"] = decision.value
        if provenance is not None:
            value["provenance"] = [*value.get("provenance", ()), dict(provenance)]
        updated = DesignExecutionPackage.create(**value)
        self.repository.save_package(updated)
        return updated


__all__ = ["Coordinator", "StepResult"]
