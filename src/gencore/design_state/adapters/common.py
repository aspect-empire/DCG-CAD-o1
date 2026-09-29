"""Shared pure helpers for design-state input adapters."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from gencore.events import canonical_hash

from ..proposals import GraphOperation, GraphProposal


def edge_operation(source: str, target: str, relation: str, *, evidence: Sequence[Mapping[str, Any]] = ()) -> GraphOperation:
    uid = "edge:" + canonical_hash({"source": source, "target": target, "relation": relation})
    return GraphOperation(
        "add_edge",
        uid,
        {
            "uid": uid,
            "source": source,
            "target": target,
            "relation": relation,
            "state": "observed",
            "evidence": list(evidence),
        },
    )


def proposal_from_operations(
    *,
    run_id: str,
    base_version: str,
    operations: Sequence[GraphOperation],
    premise_event_ids: Sequence[str],
    read_set: Sequence[str] = (),
) -> GraphProposal:
    return GraphProposal.create(
        run_id,
        base_version,
        read_set,
        tuple(operation.target for operation in operations),
        operations,
        premise_event_ids,
        ("schema", "entity_identity", "write_set"),
    )
