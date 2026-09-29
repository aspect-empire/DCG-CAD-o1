"""Traceable deterministic proposal construction for graph invalidation."""

from collections.abc import Mapping, Sequence, Set

from .dependencies import affected_closure
from .proposals import GraphOperation, GraphProposal


def build_invalidation_proposal(
    *,
    run_id: str,
    base_version: str,
    dependencies: Mapping[str, Set[str]],
    changed_uids: Set[str],
    premise_event_ids: Sequence[str],
) -> GraphProposal:
    downstream = affected_closure(dependencies, changed_uids) - set(changed_uids)
    premises = tuple(sorted(set(premise_event_ids)))
    operations = tuple(
        GraphOperation(
            "set_node_state",
            uid,
            {"state": "unknown", "invalidated_by": list(premises), "state_reason": "upstream_change"},
        )
        for uid in sorted(downstream)
    )
    return GraphProposal.create(
        run_id,
        base_version,
        tuple(sorted(changed_uids)),
        tuple(sorted(downstream)),
        operations,
        premises,
        ("schema", "dependency_closure", "write_set"),
    )
