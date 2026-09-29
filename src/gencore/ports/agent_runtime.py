"""Agent runtime port and deterministic scripted adapter."""

from __future__ import annotations

from typing import Any, Mapping, Protocol

from gencore.orchestration.contracts import AgentOutcome


class AgentRuntime(Protocol):
    def invoke(
        self,
        task: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> AgentOutcome: ...


class ScriptedAgentRuntime:
    def __init__(self, outcomes: Mapping[str, AgentOutcome]) -> None:
        self.outcomes = dict(outcomes)
        self.calls: list[tuple[str, str]] = []

    def invoke(
        self,
        task: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> AgentOutcome:
        task_id = str(task["task_id"])
        graph_version = str(context["graph_version"])
        self.calls.append((task_id, graph_version))
        try:
            return self.outcomes[task_id]
        except KeyError as exc:
            raise KeyError(f"no scripted outcome for task: {task_id}") from exc


__all__ = ["AgentRuntime", "ScriptedAgentRuntime"]
