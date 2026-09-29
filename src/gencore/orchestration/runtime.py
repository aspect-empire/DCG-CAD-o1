"""Portable closed-loop runtime over the one-step coordinator."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Callable, Mapping
from uuid import uuid4

from gencore.design_state import GraphOperation, GraphProposal
from gencore.design_state.dependencies import DependencyEdge, affected_subgraph
from gencore.design_state.ontology import View
from gencore.design_state.records import DesignNode
from gencore.ports import AllowReadOnlyApproval, ScriptedAgentRuntime, ScriptedToolExecutor
from gencore.workspace import WorkspaceLayout

from .contracts import AgentOutcome, DesignDecision, DesignExecutionPackage
from .coordinator import Coordinator, StepResult
from .decision import DecisionEvaluator
from .evidence_router import EvidenceRouter
from .mechanisms import MechanismControls
from .roles import AgentRole, default_role_policies
from .state_repository import WorkspaceStateRepository
from .task_graph import DefaultTaskBuilder
from .transaction_gateway import TransactionGateway


@dataclass(frozen=True)
class RuntimeResult:
    decision: DesignDecision
    steps: int
    stop_reason: str
    graph_version: str
    dispatched_task_ids: tuple[str, ...]
    step_results: tuple[StepResult, ...]
    stage_history: tuple[str, ...] = ()
    cad_operations: tuple[str, ...] = ()
    predicted_affected: tuple[str, ...] = ()
    actual_rebuilt: tuple[str, ...] = ()
    evidence_coverage: float = 0.0
    final_graph_hash: str = ""
    final_package_hash: str = ""
    evidence_mode: str = "runtime"

    def semantic_summary(self) -> dict[str, Any]:
        return {
            "evidence_mode": self.evidence_mode,
            "decision": self.decision.value,
            "stage_history": list(self.stage_history),
            "cad_operations": list(self.cad_operations),
            "predicted_affected": list(self.predicted_affected),
            "actual_rebuilt": list(self.actual_rebuilt),
            "evidence_coverage": self.evidence_coverage,
            "dispatched_task_ids": list(self.dispatched_task_ids),
        }


class DesignRuntime:
    def __init__(
        self,
        coordinator: Coordinator,
        *,
        cancelled: Callable[[], bool] | None = None,
    ) -> None:
        self.coordinator = coordinator
        self.cancelled = cancelled or (lambda: False)

    def run(self, run_id: str, *, max_steps: int = 50) -> RuntimeResult:
        if max_steps < 1:
            raise ValueError("max_steps must be positive")
        controls = getattr(self.coordinator, "mechanism_controls", None)
        if controls is not None and not controls.professional_task_loop:
            max_steps = 1
        results: list[StepResult] = []
        dispatched: list[str] = []
        for _ in range(max_steps):
            if self.cancelled():
                return self._result(DesignDecision.ABSTAINED, "cancelled", results, dispatched)
            step = self.coordinator.step(run_id)
            results.append(step)
            if step.dispatched_task_id:
                dispatched.append(step.dispatched_task_id)
            if step.decision is not DesignDecision.RUNNING:
                return self._result(
                    step.decision,
                    "terminal_decision",
                    results,
                    dispatched,
                )
            if step.dispatched_task_id:
                continue
            return self._result(
                step.decision,
                "terminal_decision"
                if step.decision is not DesignDecision.RUNNING
                else "no_ready_tasks",
                results,
                dispatched,
            )
        return self._result(DesignDecision.ABSTAINED, "max_steps", results, dispatched)

    @staticmethod
    def _result(
        decision: DesignDecision,
        reason: str,
        results: list[StepResult],
        dispatched: list[str],
    ) -> RuntimeResult:
        return RuntimeResult(
            decision,
            len(results),
            reason,
            results[-1].graph_version if results else "",
            tuple(dispatched),
            tuple(results),
        )


def replay_fixture(
    input_path: str | Path,
    scripted_outcomes_path: str | Path,
    output_root: str | Path,
    *,
    mechanism_controls: MechanismControls | None = None,
) -> RuntimeResult:
    package_value = json.loads(Path(input_path).read_text(encoding="utf-8"))
    outcomes_value = json.loads(Path(scripted_outcomes_path).read_text(encoding="utf-8"))
    predicted, paths = _fixture_affected(outcomes_value.get("repair_analysis", {}))
    _validate_fixture_claims(outcomes_value, predicted)
    run_id = str(package_value["run_id"])
    repository = WorkspaceStateRepository(output_root, run_id=run_id)
    package_value.pop("package_id", None)
    package_value["graph_version"] = repository.head.version_id
    repository.save_package(DesignExecutionPackage.create(**package_value))
    scripted_values = dict(outcomes_value.get("agent_outcomes", {}))

    class FixtureAgentRuntime:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str]] = []

        def invoke(
            self, task: Mapping[str, Any], context: Mapping[str, Any]
        ) -> AgentOutcome:
            task_id = str(task["task_id"])
            self.calls.append((task_id, str(context["graph_version"])))
            try:
                value = dict(scripted_values[task_id])
            except KeyError as exc:
                raise KeyError(f"fixture has no outcome for task: {task_id}") from exc
            proposal = _fixture_audit_proposal(task, context, value)
            return AgentOutcome(
                status=str(value.get("status", "completed")),
                graph_proposals=(proposal.to_dict(),),
                tool_requests=tuple(value.get("tool_requests", ())),
                missing_inputs=tuple(value.get("missing_inputs", ())),
                risks=tuple(value.get("risks", ())),
                suggested_tasks=tuple(value.get("suggested_tasks", ())),
                evidence_refs=tuple(value.get("evidence_refs", ())),
                requested_decision=DesignDecision(
                    value.get("requested_decision", DesignDecision.RUNNING)
                ),
            )

    policies = default_role_policies()
    controls = mechanism_controls or MechanismControls()
    coordinator = Coordinator(
        repository=repository,
        agent_runtime=FixtureAgentRuntime(),
        role_policies=policies,
        task_builder=DefaultTaskBuilder(),
        transaction_gateway=TransactionGateway(repository, policies),
        tool_executor=ScriptedToolExecutor(outcomes_value.get("tool_outcomes", {})),
        approval_gateway=AllowReadOnlyApproval(),
        evidence_router=EvidenceRouter.default(),
        decision_evaluator=DecisionEvaluator(),
        mechanism_controls=controls,
    )
    core_result = DesignRuntime(coordinator).run(
        run_id, max_steps=int(outcomes_value.get("max_steps", 50))
    )
    final_state = dict(outcomes_value.get("final_evaluation", {}))
    final_decision = (
        DecisionEvaluator().evaluate(final_state).decision
        if final_state
        and controls.professional_task_loop
        and controls.validation_writeback
        and (
            controls.local_repair
            or not outcomes_value.get("repair_analysis")
        )
        else core_result.decision
    )
    stages = _stage_history(repository, str(package_value.get("stage", "S0_INITIALIZE")))
    cad_operations = tuple(
        str(item["kind"])
        for item in package_value.get("operation_sequence", ())
        if item.get("kind")
    )
    actual_rebuilt = tuple(
        sorted(
            {
                str(item)
                for item in outcomes_value.get("repair_analysis", {}).get(
                    "actual_rebuilt", ()
                )
            }
        )
    )
    final_package = repository.load_current_package()
    result = replace(
        core_result,
        decision=final_decision,
        stage_history=stages,
        cad_operations=cad_operations,
        predicted_affected=predicted,
        actual_rebuilt=actual_rebuilt,
        evidence_coverage=float(
            final_state.get("validation_coverage", 0.0)
        ),
        final_graph_hash=repository.head.graph_hash,
        final_package_hash=final_package.package_id,
        evidence_mode="scripted_simulation",
    )
    _write_fixture_reports(
        output_root,
        result,
        outcomes_value,
        paths,
    )
    return result


_AUDIT_NODE_TYPES = {
    AgentRole.SCENE_CONSTRAINT: (View.RESULT_EVIDENCE, "Evidence"),
    AgentRole.SOLUTION_PARAMETER: (View.PARAMETER_RULE, "Derivation"),
    AgentRole.GEOMETRY_PLANNING: (View.PROCESS_TOOL, "ModelPlan"),
    AgentRole.CAD_EXECUTOR: (View.PROCESS_TOOL, "Execution"),
    AgentRole.VALIDATION: (View.RESULT_EVIDENCE, "Validation"),
    AgentRole.REPAIR_REFLECTION: (View.PROCESS_TOOL, "RepairPlan"),
}


def _fixture_audit_proposal(
    task: Mapping[str, Any],
    context: Mapping[str, Any],
    value: Mapping[str, Any],
) -> GraphProposal:
    role = AgentRole(task["role"])
    view, node_type = _AUDIT_NODE_TYPES[role]
    node = DesignNode.create(
        view,
        node_type,
        str(task["task_id"]),
        {
            "task_id": task["task_id"],
            "stage": task["stage"],
            "status": value.get("status", "completed"),
            "evidence_refs": list(value.get("evidence_refs", ())),
            "fixture_record": dict(value.get("record", {})),
        },
        (),
    )
    operation = GraphOperation("add_node", node.uid, node.to_dict())
    return GraphProposal.create(
        str(context["execution_package"]["run_id"]),
        str(context["graph_version"]),
        (),
        (node.uid,),
        (operation,),
        (),
        ("schema", "role_permission", "fixture_replay"),
    )


def _stage_history(
    repository: WorkspaceStateRepository, initial_stage: str
) -> tuple[str, ...]:
    result = [initial_stage]
    for event in repository.events:
        if event.kind != "proposal.committed":
            continue
        for operation in event.proposal.operations:
            if operation.kind != "add_node":
                continue
            stage = operation.value.get("attributes", {}).get("stage")
            if stage and stage not in result:
                result.append(str(stage))
    return tuple(result)


def _fixture_affected(
    value: Mapping[str, Any],
) -> tuple[tuple[str, ...], tuple[dict[str, Any], ...]]:
    if not value:
        return (), ()
    edges = tuple(
        DependencyEdge(
            str(item["source"]),
            str(item["target"]),
            str(item["relation"]),
            float(item.get("confidence", 1.0)),
        )
        for item in value.get("edges", ())
    )
    result = affected_subgraph(
        edges,
        starts={str(item) for item in value.get("starts", ())},
        allowed_relations={
            str(item) for item in value.get("allowed_relations", ())
        },
        max_depth=int(value.get("max_depth", 5)),
        protected={str(item) for item in value.get("protected", ())},
    )
    paths = tuple(
        {
            "start": item.start,
            "target": item.target,
            "node_uids": list(item.node_uids),
            "relations": list(item.relations),
            "confidence": item.confidence,
        }
        for item in result.paths
    )
    return result.node_uids, paths


def _validate_fixture_claims(
    outcomes: Mapping[str, Any],
    predicted_affected: tuple[str, ...],
) -> None:
    """Reject internally inconsistent scripted simulation claims."""

    repair = dict(outcomes.get("repair_analysis", {}))
    protected = {str(item) for item in repair.get("protected", ())}
    actual = {str(item) for item in repair.get("actual_rebuilt", ())}
    overlap = sorted(protected & actual)
    if overlap:
        raise ValueError(
            "scripted repair rebuilds protected features: " + ", ".join(overlap)
        )
    outside = sorted(actual - set(predicted_affected))
    if outside:
        raise ValueError(
            "scripted repair rebuilds nodes outside the predicted set: "
            + ", ".join(outside)
        )
    for manifest in outcomes.get("cad_manifests", ()):
        if manifest.get("status") != "completed":
            raise ValueError("scripted CAD manifests must be completed")
    final = dict(outcomes.get("final_evaluation", {}))
    if final and not final.get("evidence_refs"):
        raise ValueError("scripted final evaluation requires evidence_refs")


def _write_fixture_reports(
    output_root: str | Path,
    result: RuntimeResult,
    outcomes: Mapping[str, Any],
    affected_paths: tuple[dict[str, Any], ...],
) -> None:
    layout = WorkspaceLayout(output_root, ("runs/reports",)).create()
    reports = {
        "fixture_summary.json": result.semantic_summary(),
        "task_trace.json": {
            "tasks": list(result.dispatched_task_ids),
            "stages": list(result.stage_history),
        },
        "candidate_match.json": outcomes.get("candidate_match", {}),
        "parameter_derivations.json": outcomes.get("parameter_derivations", {}),
        "cad_manifests.json": {
            "operations": list(result.cad_operations),
            "manifests": outcomes.get("cad_manifests", []),
        },
        "validation_evidence.json": outcomes.get("final_evaluation", {}),
        "affected_subgraph.json": {
            "predicted_affected": list(result.predicted_affected),
            "paths": list(affected_paths),
            "actual_rebuilt": list(result.actual_rebuilt),
        },
    }
    for name, value in reports.items():
        layout.atomic_write_json(f"runs/reports/{name}", value)


def main(argv: list[str] | None = None) -> int:
    """Run a checked-in scripted fixture and emit its acceptance evidence."""

    parser = argparse.ArgumentParser(
        description="Replay a GenCore orchestration fixture deterministically."
    )
    parser.add_argument("input_path", type=Path)
    parser.add_argument(
        "--scripted",
        action="store_true",
        help="Use scripted_outcomes.json beside the input file.",
    )
    parser.add_argument("--scripted-outcomes", type=Path)
    parser.add_argument("--output-root", type=Path)
    args = parser.parse_args(argv)
    if not args.scripted and args.scripted_outcomes is None:
        parser.error("only scripted replay is available; pass --scripted")

    input_path = args.input_path.resolve()
    outcomes_path = (
        args.scripted_outcomes.resolve()
        if args.scripted_outcomes is not None
        else input_path.with_name("scripted_outcomes.json")
    )
    if not input_path.is_file():
        parser.error(f"input file does not exist: {input_path}")
    if not outcomes_path.is_file():
        parser.error(f"scripted outcomes do not exist: {outcomes_path}")
    if args.output_root is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        output_root = (
            Path.cwd()
            / "outputs"
            / "orchestration"
            / f"{input_path.parent.name}-{stamp}-{uuid4().hex[:8]}"
        )
    else:
        output_root = args.output_root.resolve()
        if output_root.exists() and any(output_root.iterdir()):
            parser.error(
                "--output-root must be absent or empty for deterministic replay"
            )

    result = replay_fixture(input_path, outcomes_path, output_root)
    payload = {
        **result.semantic_summary(),
        "graph_version": result.graph_version,
        "final_graph_hash": result.final_graph_hash,
        "final_package_hash": result.final_package_hash,
        "output_root": str(output_root),
        "stop_reason": result.stop_reason,
        "steps": result.steps,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


__all__ = ["DesignRuntime", "RuntimeResult", "main", "replay_fixture"]


if __name__ == "__main__":
    raise SystemExit(main())
