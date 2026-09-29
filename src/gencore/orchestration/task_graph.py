"""Deterministic dependency and write-lock scheduling for design tasks."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from gencore.events import canonical_hash

from .contracts import Stage
from .roles import AgentRole


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class DesignTask:
    task_id: str
    kind: str
    role: AgentRole
    stage: Stage
    depends_on: tuple[str, ...] = ()
    read_set: tuple[str, ...] = ()
    write_set: tuple[str, ...] = ()
    idempotency_key: str | None = None
    status: TaskStatus = TaskStatus.PENDING
    attempt_no: int = 0
    max_attempts: int = 2
    risk_rank: int = 1
    payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.task_id or not self.kind:
            raise ValueError("task_id and kind must be non-empty")
        object.__setattr__(self, "role", AgentRole(self.role))
        object.__setattr__(self, "stage", Stage(self.stage))
        object.__setattr__(self, "status", TaskStatus(self.status))
        object.__setattr__(self, "depends_on", tuple(sorted(set(self.depends_on))))
        object.__setattr__(self, "read_set", tuple(sorted(set(self.read_set))))
        object.__setattr__(self, "write_set", tuple(sorted(set(self.write_set))))
        object.__setattr__(
            self,
            "payload",
            MappingProxyType(
                {str(key): _plain(value) for key, value in self.payload.items()}
            ),
        )
        if self.attempt_no < 0 or self.max_attempts < 1:
            raise ValueError("attempt_no must be nonnegative and max_attempts must be positive")
        if self.risk_rank < 0:
            raise ValueError("risk_rank must be nonnegative")
        if self.task_id in self.depends_on:
            raise ValueError("task cannot depend on itself")
        if not self.idempotency_key:
            identity = {
                "task_id": self.task_id,
                "kind": self.kind,
                "role": self.role.value,
                "stage": self.stage.value,
                "read_set": self.read_set,
                "write_set": self.write_set,
                "payload": dict(self.payload),
            }
            object.__setattr__(self, "idempotency_key", "task-key:" + canonical_hash(identity))

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "kind": self.kind,
            "role": self.role.value,
            "stage": self.stage.value,
            "depends_on": list(self.depends_on),
            "read_set": list(self.read_set),
            "write_set": list(self.write_set),
            "idempotency_key": self.idempotency_key,
            "status": self.status.value,
            "attempt_no": self.attempt_no,
            "max_attempts": self.max_attempts,
            "risk_rank": self.risk_rank,
            "payload": dict(self.payload),
        }


class TaskGraph:
    def __init__(
        self,
        tasks: Sequence[DesignTask],
        locked_write_uids: set[str] | frozenset[str] = frozenset(),
    ) -> None:
        ordered = tuple(tasks)
        identifiers = [task.task_id for task in ordered]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("duplicate task IDs are not allowed")
        known = set(identifiers)
        for item in ordered:
            missing = set(item.depends_on) - known
            if missing:
                raise ValueError(
                    f"unknown dependency for {item.task_id}: {', '.join(sorted(missing))}"
                )
        self.tasks = ordered
        self.locked_write_uids = frozenset(locked_write_uids)
        self._by_id = {task.task_id: task for task in ordered}

    def ready(self) -> tuple[DesignTask, ...]:
        stage_rank = {stage: index for index, stage in enumerate(Stage)}
        candidates = []
        for item in self.tasks:
            if item.status is not TaskStatus.PENDING or item.attempt_no >= item.max_attempts:
                continue
            if any(
                self._by_id[dependency].status is not TaskStatus.COMPLETED
                for dependency in item.depends_on
            ):
                continue
            if set(item.write_set) & self.locked_write_uids:
                continue
            candidates.append(item)
        candidates.sort(
            key=lambda item: (item.risk_rank, stage_rank[item.stage], item.task_id)
        )

        selected: list[DesignTask] = []
        selected_writes: set[str] = set()
        for item in candidates:
            if set(item.write_set) & selected_writes:
                continue
            selected.append(item)
            selected_writes.update(item.write_set)
        return tuple(selected)


class DefaultTaskBuilder:
    """Build a deterministic task DAG from an immutable execution package."""

    def build(self, package: Any, snapshot: Mapping[str, Any]) -> TaskGraph:
        del snapshot
        history = tuple(package.provenance)
        completed = {
            str(item["task_id"])
            for item in history
            if item.get("status") == "completed" and item.get("task_id")
        }
        known_ids = {
            str(item["task_id"]) for item in history if item.get("task_id")
        }
        attempts = {
            task_id: sum(1 for item in history if item.get("task_id") == task_id)
            for task_id in known_ids
        }
        tasks: list[DesignTask] = []

        def add(
            task_id: str,
            kind: str,
            role: AgentRole,
            stage: Stage,
            *,
            depends_on: tuple[str, ...] = (),
            risk_rank: int,
            payload: Mapping[str, Any] | None = None,
        ) -> None:
            tasks.append(
                DesignTask(
                    task_id,
                    kind,
                    role,
                    stage,
                    depends_on=depends_on,
                    read_set=(package.graph_version,),
                    write_set=(f"task-output:{task_id}",),
                    status=TaskStatus.COMPLETED if task_id in completed else TaskStatus.PENDING,
                    attempt_no=attempts.get(task_id, 0),
                    max_attempts=3,
                    risk_rank=risk_rank,
                    payload=dict(payload or {}),
                )
            )

        previous: str | None = None
        if package.unknown_constraints:
            add(
                "task:scene",
                "resolve_scene_constraints",
                AgentRole.SCENE_CONSTRAINT,
                Stage.S1_ACTIVATE_CONSTRAINTS,
                risk_rank=0,
                payload={"unknown_constraints": list(package.unknown_constraints)},
            )
            previous = "task:scene"
        if package.design_intent.get("requires_case_matching") or package.candidate_templates:
            add(
                "task:solution",
                "match_and_calculate_solution",
                AgentRole.SOLUTION_PARAMETER,
                Stage.S1_ACTIVATE_CONSTRAINTS,
                depends_on=(previous,) if previous else (),
                risk_rank=1,
            )
            previous = "task:solution"
        if package.model_plan or package.design_intent.get("requires_geometry_plan"):
            add(
                "task:geometry",
                "plan_geometry",
                AgentRole.GEOMETRY_PLANNING,
                Stage.S2_PLAN_GEOMETRY,
                depends_on=(previous,) if previous else (),
                risk_rank=2,
            )
            previous = "task:geometry"
        if package.operation_sequence:
            add(
                "task:cad",
                "execute_staged_cad",
                AgentRole.CAD_EXECUTOR,
                Stage.S3_EXECUTE_CAD,
                depends_on=(previous,) if previous else (),
                risk_rank=3,
                payload={"operations": list(package.operation_sequence)},
            )
            previous = "task:cad"
        add(
            "task:validate",
            "validate_independently",
            AgentRole.VALIDATION,
            Stage.S4_VALIDATE,
            depends_on=(previous,) if previous else (),
            risk_rank=4,
            payload={"validation_plan": list(package.validation_plan)},
        )
        if package.conflicts or any(
            item.get("status") == "failed" for item in package.validation_evidence
        ):
            add(
                "task:repair",
                "plan_local_repair",
                AgentRole.REPAIR_REFLECTION,
                Stage.S5_REPAIR_OR_HANDOFF,
                depends_on=("task:validate",),
                risk_rank=5,
            )
        return TaskGraph(tasks)


__all__ = [
    "DefaultTaskBuilder",
    "DesignTask",
    "TaskGraph",
    "TaskStatus",
]
