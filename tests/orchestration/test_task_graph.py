import pytest

from gencore.orchestration import AgentRole, Stage
from gencore.orchestration.task_graph import DesignTask, TaskGraph, TaskStatus


def task(
    task_id,
    *,
    depends_on=(),
    write_set=(),
    status=TaskStatus.PENDING,
    attempt_no=0,
    max_attempts=2,
    risk_rank=1,
):
    return DesignTask(
        task_id=task_id,
        kind="test",
        role=AgentRole.SCENE_CONSTRAINT,
        stage=Stage.S0_INITIALIZE,
        depends_on=depends_on,
        write_set=write_set,
        status=status,
        attempt_no=attempt_no,
        max_attempts=max_attempts,
        risk_rank=risk_rank,
    )


def test_task_graph_returns_only_dependency_free_tasks_in_stable_order():
    graph = TaskGraph(
        (
            task("task:b", depends_on=("task:a",)),
            task("task:c", risk_rank=2),
            task("task:a", risk_rank=1),
        )
    )

    assert [item.task_id for item in graph.ready()] == ["task:a", "task:c"]


def test_completed_dependency_unlocks_downstream_task():
    graph = TaskGraph(
        (
            task("task:a", status=TaskStatus.COMPLETED),
            task("task:b", depends_on=("task:a",)),
        )
    )

    assert [item.task_id for item in graph.ready()] == ["task:b"]


def test_ready_tasks_do_not_overlap_active_or_selected_write_sets():
    graph = TaskGraph(
        (
            task("task:a", write_set=("node:x",), risk_rank=1),
            task("task:b", write_set=("node:x",), risk_rank=2),
            task("task:c", write_set=("node:y",), risk_rank=3),
        ),
        locked_write_uids={"node:z"},
    )

    assert [item.task_id for item in graph.ready()] == ["task:a", "task:c"]
    assert TaskGraph((task("task:z", write_set=("node:z",)),), {"node:z"}).ready() == ()


def test_exhausted_and_non_pending_tasks_are_not_ready():
    graph = TaskGraph(
        (
            task("task:exhausted", attempt_no=2, max_attempts=2),
            task("task:running", status=TaskStatus.RUNNING),
            task("task:pending"),
        )
    )

    assert [item.task_id for item in graph.ready()] == ["task:pending"]


def test_duplicate_and_missing_dependencies_are_rejected():
    with pytest.raises(ValueError, match="duplicate"):
        TaskGraph((task("task:a"), task("task:a")))
    with pytest.raises(ValueError, match="unknown dependency"):
        TaskGraph((task("task:b", depends_on=("task:missing",)),))
