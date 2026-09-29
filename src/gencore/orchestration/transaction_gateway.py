"""Role-aware validation and optimistic commit of graph proposals."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from gencore.design_state import (
    DesignStateStore,
    GraphProposal,
    ProposalValidator,
)

from .roles import AgentRole, RolePolicy


@dataclass(frozen=True)
class TransactionResult:
    status: str
    proposal_id: str
    version_id: str
    reason: str | None = None
    rebased_from: str | None = None


_ALLOWED_TRANSITIONS = {
    "unknown": {
        "candidate",
        "inferred",
        "proposed",
        "derived",
        "verified",
        "conflicted",
        "rejected",
        "superseded",
    },
    "observed": {"verified", "conflicted", "rejected", "superseded", "unknown"},
    "candidate": {
        "inferred",
        "derived",
        "verified",
        "conflicted",
        "rejected",
        "superseded",
        "unknown",
    },
    "inferred": {
        "verified",
        "conflicted",
        "rejected",
        "superseded",
        "unknown",
    },
    "proposed": {
        "derived",
        "verified",
        "conflicted",
        "rejected",
        "superseded",
        "unknown",
    },
    "derived": {
        "verified",
        "conflicted",
        "rejected",
        "superseded",
        "unknown",
    },
    "verified": {"conflicted", "rejected", "superseded", "unknown"},
    "conflicted": {
        "candidate",
        "inferred",
        "proposed",
        "derived",
        "verified",
        "rejected",
        "superseded",
        "unknown",
    },
    "rejected": {"superseded"},
    "superseded": set(),
}


class TransactionGateway:
    def __init__(
        self,
        repository: DesignStateStore,
        role_policies: Mapping[AgentRole, RolePolicy],
    ) -> None:
        self.repository = repository
        self.role_policies = dict(role_policies)

    def submit(self, role: AgentRole, proposal: GraphProposal) -> TransactionResult:
        role = AgentRole(role)
        previous_base: str | None = None
        try:
            self._validate_role(self.role_policies[role], proposal)
            changed = self._changes_since(proposal.base_version)
            stale_reads = set(proposal.read_set) & changed
            stale_writes = set(proposal.write_set) & changed
            if stale_reads:
                raise ValueError("stale reads: " + ", ".join(sorted(stale_reads)))
            if stale_writes:
                raise ValueError(
                    "overlapping stale writes: " + ", ".join(sorted(stale_writes))
                )
            if proposal.base_version != self.repository.head.version_id:
                previous_base = proposal.base_version
                proposal = GraphProposal.create(
                    proposal.run_id,
                    self.repository.head.version_id,
                    proposal.read_set,
                    proposal.write_set,
                    proposal.operations,
                    proposal.premise_event_ids,
                    proposal.validation_plan,
                )
            ProposalValidator(self.repository.head.version_id, set()).validate(proposal)
            self._validate_state_transitions(proposal)
            version = self.repository.commit(proposal)
        except (KeyError, TypeError, ValueError) as exc:
            attempt = self.repository.reject(proposal, str(exc))
            return TransactionResult(
                "rejected",
                proposal.proposal_id,
                attempt.version_id,
                str(exc),
                previous_base,
            )
        return TransactionResult(
            "committed",
            proposal.proposal_id,
            version.version_id,
            None,
            previous_base,
        )

    def _changes_since(self, base_version: str) -> set[str]:
        if base_version == self.repository.head.version_id:
            return set()
        if base_version not in self.repository.snapshots:
            raise ValueError(f"unknown base version: {base_version}")
        committed = {
            event.version.version_id: event
            for event in self.repository.events
            if event.kind == "proposal.committed"
        }
        cursor = self.repository.head.version_id
        changes: set[str] = set()
        while cursor != base_version:
            try:
                event = committed[cursor]
            except KeyError as exc:
                raise ValueError(
                    f"base version is not an ancestor of the active head: {base_version}"
                ) from exc
            changes.update(event.proposal.write_set)
            cursor = event.version.parent_version or ""
        return changes

    @staticmethod
    def _validate_role(policy: RolePolicy, proposal: GraphProposal) -> None:
        for operation in proposal.operations:
            if not policy.allows_operation(operation.kind):
                raise ValueError(f"role cannot perform {operation.kind}")
            if operation.kind == "add_node":
                node_type = str(operation.value.get("node_type", ""))
                if not policy.allows_node_write(node_type):
                    raise ValueError(f"role cannot create {node_type or 'untyped node'}")

    def _validate_state_transitions(self, proposal: GraphProposal) -> None:
        snapshot = self.repository.snapshot()
        for operation in proposal.operations:
            if operation.kind != "set_node_state":
                continue
            try:
                current = str(snapshot["nodes"][operation.target]["state"])
            except KeyError as exc:
                raise ValueError(
                    f"state transition target does not exist: {operation.target}"
                ) from exc
            target = str(operation.value.get("state", ""))
            if current == target:
                continue
            if target not in _ALLOWED_TRANSITIONS.get(current, set()):
                raise ValueError(
                    f"illegal state transition for {operation.target}: {current} -> {target}"
                )


__all__ = ["TransactionGateway", "TransactionResult"]
