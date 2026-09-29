"""State repository port for versioned design graphs."""

from __future__ import annotations

from typing import Any, Mapping, Protocol

from gencore.design_state import GraphProposal, GraphVersion


class StateRepository(Protocol):
    @property
    def head(self) -> GraphVersion: ...

    def read_snapshot(self, version_id: str | None = None) -> Mapping[str, Any]: ...

    def changes_since(self, base_version: str) -> set[str]: ...

    def commit(self, proposal: GraphProposal) -> GraphVersion: ...

    def reject(self, proposal: GraphProposal, reason: str) -> GraphVersion: ...


__all__ = ["StateRepository"]
