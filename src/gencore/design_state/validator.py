"""Validation and optimistic write-conflict checks for graph proposals."""

from dataclasses import dataclass
from typing import Iterable

from .proposals import GraphProposal


class ProposalConflict(ValueError):
    """Raised when a stale proposal overlaps changes made after its base version."""


@dataclass(frozen=True)
class ValidationResult:
    proposal_id: str
    rebased_to: str


class ProposalValidator:
    def __init__(self, current_version: str, changed_since_base: Iterable[str]):
        if not current_version:
            raise ValueError("current_version must be a non-empty string")
        self.current_version = current_version
        self.changed_since_base = frozenset(changed_since_base)

    def validate(self, proposal: GraphProposal) -> ValidationResult:
        overlap = set(proposal.write_set) & self.changed_since_base
        if proposal.base_version != self.current_version and overlap:
            raise ProposalConflict("overlapping stale writes: " + ", ".join(sorted(overlap)))
        undeclared = {operation.target for operation in proposal.operations} - set(proposal.write_set)
        if undeclared:
            raise ValueError("operation targets missing from write_set: " + ", ".join(sorted(undeclared)))
        return ValidationResult(proposal.proposal_id, self.current_version)
