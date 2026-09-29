"""Framework-neutral enforcement of orchestration mechanism switches."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class MechanismControls:
    professional_task_loop: bool = True
    fixed_stage_order: bool = False
    multi_agent: bool = True
    structured_state: bool = True
    open_world_states: bool = True
    version_transactions: bool = True
    read_write_sets: bool = True
    validation_writeback: bool = True
    provenance_tracking: bool = True
    local_repair: bool = True
    failure_strategy: str = "affected_subgraph"

    def project_state(self, snapshot: Mapping[str, Any]) -> dict[str, Any]:
        if not self.structured_state:
            return {"nodes": {}, "edges": {}}
        nodes = {
            str(uid): self._node(record)
            for uid, record in snapshot.get("nodes", {}).items()
            if self.open_world_states
            or record.get("state") not in {"unknown", "conflicted"}
        }
        visible = set(nodes)
        edges = {
            str(uid): self._edge(record)
            for uid, record in snapshot.get("edges", {}).items()
            if record.get("source") in visible and record.get("target") in visible
        }
        return {"nodes": nodes, "edges": edges}

    def allows_graph_writeback(self, role: str) -> bool:
        if not self.version_transactions or not self.read_write_sets:
            return False
        return self.validation_writeback or role != "validation"

    def _node(self, record: Mapping[str, Any]) -> dict[str, Any]:
        result = dict(record)
        if not self.provenance_tracking:
            result["evidence"] = []
        return result

    def _edge(self, record: Mapping[str, Any]) -> dict[str, Any]:
        result = dict(record)
        if not self.provenance_tracking:
            result["evidence"] = []
        return result


__all__ = ["MechanismControls"]
