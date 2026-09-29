"""AgentRuntime adapter for role-specific compiled DeepAgent specialists."""

from __future__ import annotations

import json
from typing import Any, Mapping

from gencore.events import canonical_hash
from gencore.orchestration import AgentOutcome, DesignDecision
from gencore.orchestration.roles import AgentRole


class DeepAgentRuntime:
    def __init__(
        self,
        specialists: Mapping[AgentRole, Any],
        *,
        repository: Any | None = None,
        recursion_limit: int = 6,
    ) -> None:
        self.specialists = {
            AgentRole(role): compiled for role, compiled in specialists.items()
        }
        self.repository = repository
        self.recursion_limit = int(recursion_limit)
        self.usage_evidence: list[dict[str, Any]] = []
        self.call_records: list[dict[str, Any]] = []

    def invoke(
        self,
        task: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> AgentOutcome:
        role = AgentRole(task["role"])
        try:
            compiled = self.specialists[role]
        except KeyError as exc:
            raise ValueError(f"no compiled specialist for role: {role.value}") from exc
        payload = self._fresh_context(task, context)
        payload["messages"] = [{
            "role": "user",
            "content": json.dumps(
                {
                    "task": payload["task"],
                    "graph_version": payload["graph_version"],
                    "state_view": payload["state_view"],
                    "execution_package": payload["execution_package"],
                    "allowed_tool_schemas": payload["allowed_tool_schemas"],
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
        }]
        raw = compiled.invoke(
            payload,
            config={"recursion_limit": self.recursion_limit},
        )
        if isinstance(raw, AgentOutcome):
            outcome = raw
            usage = {}
        elif isinstance(raw, Mapping) and isinstance(
            raw.get("structured_response"), (Mapping, AgentOutcome)
        ):
            structured = raw["structured_response"]
            outcome = (
                structured
                if isinstance(structured, AgentOutcome)
                else self._outcome(structured)
            )
            usage = dict(raw.get("usage_metadata") or {})
        else:
            raise ValueError("DeepAgent specialist must return a structured AgentOutcome")

        if usage:
            evidence_id = "usage:" + canonical_hash(
                {
                    "task_id": str(task["task_id"]),
                    "role": role.value,
                    "usage": usage,
                }
            )
            self.usage_evidence.append(
                {
                    "evidence_id": evidence_id,
                    "task_id": str(task["task_id"]),
                    "role": role.value,
                    "usage": usage,
                }
            )
            outcome = AgentOutcome(
                status=outcome.status,
                graph_proposals=outcome.graph_proposals,
                tool_requests=outcome.tool_requests,
                missing_inputs=outcome.missing_inputs,
                risks=outcome.risks,
                blocker_ids=outcome.blocker_ids,
                suggested_tasks=outcome.suggested_tasks,
                evidence_refs=(*outcome.evidence_refs, evidence_id),
                requested_decision=outcome.requested_decision,
            )
        self.call_records.append({
            "task_id": str(task["task_id"]),
            "role": role.value,
            "status": outcome.status,
            "usage": usage,
        })
        return outcome

    def _fresh_context(
        self, task: Mapping[str, Any], context: Mapping[str, Any]
    ) -> dict[str, Any]:
        graph_version = str(context["graph_version"])
        state_view = dict(context.get("state_view", {}))
        package = dict(context.get("execution_package", {}))
        if (
            self.repository is not None
            and graph_version != self.repository.head.version_id
        ):
            graph_version = self.repository.head.version_id
            state_view = self.repository.read_snapshot(graph_version)
            package = self.repository.load_current_package().to_dict()
        return {
            "task": dict(task),
            "graph_version": graph_version,
            "state_view": state_view,
            "execution_package": package,
            "allowed_tool_schemas": list(
                context.get("allowed_tool_schemas")
                or context.get("allowed_tools", ())
            ),
        }

    @staticmethod
    def _outcome(value: Mapping[str, Any]) -> AgentOutcome:
        requested = DesignDecision(
            value.get("requested_decision", DesignDecision.RUNNING)
        )
        return AgentOutcome(
            status=str(value["status"]),
            graph_proposals=tuple(value.get("graph_proposals", ())),
            tool_requests=tuple(value.get("tool_requests", ())),
            missing_inputs=tuple(value.get("missing_inputs", ())),
            risks=tuple(value.get("risks", ())),
            blocker_ids=tuple(value.get("blocker_ids", ())),
            suggested_tasks=tuple(value.get("suggested_tasks", ())),
            evidence_refs=tuple(value.get("evidence_refs", ())),
            requested_decision=requested,
        )


__all__ = ["DeepAgentRuntime"]
