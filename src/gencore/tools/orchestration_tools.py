"""Read-only inspection tools for the portable orchestration runtime."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from gencore.orchestration.state_repository import WorkspaceStateRepository
from gencore.orchestration.task_graph import DefaultTaskBuilder
from gencore.tool_registry import ToolSpec


OBJECT_SCHEMA = {"type": "object"}


def _repository(payload: dict[str, Any], workspace_root: str | Path | None):
    root = workspace_root or payload.get("workspace_root")
    if root is None:
        raise ValueError("workspace_root is required")
    run_id = str(payload.get("run_id", ""))
    if not run_id:
        raise ValueError("run_id is required")
    return WorkspaceStateRepository(root, run_id=run_id)


def inspect_state(
    payload: dict[str, Any], *, workspace_root: str | Path | None = None
) -> dict[str, Any]:
    repository = _repository(payload, workspace_root)
    package = repository.load_current_package()
    return {
        "run_id": repository.run_id,
        "head": repository.head.to_dict(),
        "package": package.to_dict(),
        "snapshot": repository.read_snapshot(),
    }


def preview_tasks(
    payload: dict[str, Any], *, workspace_root: str | Path | None = None
) -> dict[str, Any]:
    repository = _repository(payload, workspace_root)
    package = repository.load_current_package()
    graph = DefaultTaskBuilder().build(package, repository.read_snapshot())
    return {
        "tasks": [item.to_dict() for item in graph.tasks],
        "ready_task_ids": [item.task_id for item in graph.ready()],
    }


def orchestration_tool_specs(
    *, workspace_root: str | Path | None = None
) -> list[ToolSpec]:
    return [
        ToolSpec(
            "orchestration.state.inspect",
            "Inspect the current versioned design package and graph.",
            OBJECT_SCHEMA,
            OBJECT_SCHEMA,
            "read_only",
            "offline",
            lambda payload: inspect_state(payload, workspace_root=workspace_root),
        ),
        ToolSpec(
            "orchestration.tasks.preview",
            "Preview deterministic ready tasks without dispatching them.",
            OBJECT_SCHEMA,
            OBJECT_SCHEMA,
            "read_only",
            "offline",
            lambda payload: preview_tasks(payload, workspace_root=workspace_root),
        ),
    ]


__all__ = ["inspect_state", "orchestration_tool_specs", "preview_tasks"]
