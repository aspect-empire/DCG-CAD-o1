"""Immutable graph versions and replayable proposal outcome events."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from gencore.events import canonical_hash

from .proposals import GraphProposal
from .records import _freeze, _thaw
from .reducer import reduce_operations


@dataclass(frozen=True)
class GraphVersion:
    version_id: str
    parent_version: str | None
    graph_hash: str
    status: str
    proposal_id: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "version_id": self.version_id,
            "parent_version": self.parent_version,
            "graph_hash": self.graph_hash,
            "status": self.status,
            "proposal_id": self.proposal_id,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "GraphVersion":
        return cls(
            str(value["version_id"]),
            value.get("parent_version"),
            str(value["graph_hash"]),
            str(value["status"]),
            value.get("proposal_id"),
        )


@dataclass(frozen=True)
class VersionEvent:
    kind: str
    version: GraphVersion
    proposal: GraphProposal
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "version": self.version.to_dict(),
            "proposal": self.proposal.to_dict(),
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "VersionEvent":
        return cls(
            str(value["kind"]),
            GraphVersion.from_dict(value["version"]),
            GraphProposal.from_dict(value["proposal"]),
            value.get("reason"),
        )


class DesignStateStore:
    def __init__(self) -> None:
        empty = _freeze({"nodes": {}, "edges": {}})
        graph_hash = canonical_hash(empty)
        version_id = "ver:" + canonical_hash({"parent_version": None, "graph_hash": graph_hash})
        self._snapshots: dict[str, Mapping[str, Any]] = {version_id: empty}
        self.head = GraphVersion(version_id, None, graph_hash, "committed", None)
        self._events: list[VersionEvent] = []

    @property
    def events(self) -> tuple[VersionEvent, ...]:
        return tuple(self._events)

    @property
    def snapshots(self) -> Mapping[str, Mapping[str, Any]]:
        return MappingProxyType(self._snapshots)

    def snapshot(self, version_id: str | None = None) -> dict[str, Any]:
        return _thaw(self._snapshots[version_id or self.head.version_id])

    def commit(self, proposal: GraphProposal) -> GraphVersion:
        graph = reduce_operations(self._snapshots[self.head.version_id], proposal.operations)
        graph_hash = canonical_hash(graph)
        version_id = "ver:" + canonical_hash(
            {"parent_version": self.head.version_id, "graph_hash": graph_hash, "proposal_id": proposal.proposal_id}
        )
        version = GraphVersion(version_id, self.head.version_id, graph_hash, "committed", proposal.proposal_id)
        self._snapshots[version.version_id] = _freeze(graph)
        self._events.append(VersionEvent("proposal.committed", version, proposal))
        self.head = version
        return version

    def reject(self, proposal: GraphProposal, reason: str) -> GraphVersion:
        version_id = "attempt:" + canonical_hash(
            {"parent_version": self.head.version_id, "proposal_id": proposal.proposal_id, "reason": reason}
        )
        attempt = GraphVersion(
            version_id,
            self.head.version_id,
            self.head.graph_hash,
            "rejected",
            proposal.proposal_id,
        )
        self._events.append(VersionEvent("proposal.rejected", attempt, proposal, reason))
        return attempt

    @classmethod
    def from_events(cls, events: Sequence[VersionEvent]) -> "DesignStateStore":
        store = cls()
        for event in events:
            if event.kind == "proposal.committed":
                actual = store.commit(event.proposal)
            elif event.kind == "proposal.rejected":
                actual = store.reject(event.proposal, event.reason or "")
            else:
                raise ValueError(f"unsupported version event: {event.kind}")
            if actual != event.version:
                raise ValueError(f"version event does not replay deterministically: {event.version.version_id}")
        return store
