import json

import pytest

from gencore.design_state import GraphOperation, GraphProposal
from gencore.design_state.versions import DesignStateStore, VersionEvent


def proposal(base_version, operations, *, run_id="run-1"):
    return GraphProposal.create(
        run_id,
        base_version,
        (),
        tuple(operation.target for operation in operations),
        operations,
        premise_event_ids=("evt:" + "a" * 64,),
        validation_plan=("schema", "write_set"),
    )


def add_node_proposal(base_version):
    operation = GraphOperation(
        "add_node",
        "node:foundation",
        {
            "uid": "node:foundation",
            "view": "product_function",
            "node_type": "Foundation",
            "state": "observed",
            "evidence": [],
        },
    )
    return proposal(base_version, [operation])


def test_committed_versions_replay_to_identical_hash():
    store = DesignStateStore()
    first = store.commit(add_node_proposal(store.head.version_id))

    encoded = json.dumps([event.to_dict() for event in store.events], ensure_ascii=False)
    events = [VersionEvent.from_dict(item) for item in json.loads(encoded)]
    replayed = DesignStateStore.from_events(events)

    assert replayed.head.version_id == first.version_id
    assert replayed.head.graph_hash == first.graph_hash
    assert replayed.snapshot()["nodes"]["node:foundation"]["state"] == "observed"


def test_rejected_attempt_is_preserved_without_changing_head():
    store = DesignStateStore()
    original = store.head.version_id
    rejected = add_node_proposal("ver:stale")

    attempt = store.reject(rejected, "unit mismatch")

    assert store.head.version_id == original
    assert attempt.status == "rejected"
    assert attempt.parent_version == original
    assert store.events[-1].kind == "proposal.rejected"
    assert store.events[-1].reason == "unit mismatch"


def test_supersession_closes_current_state_without_mutating_parent_snapshot():
    store = DesignStateStore()
    first = store.commit(add_node_proposal(store.head.version_id))
    supersede = proposal(
        first.version_id,
        [GraphOperation("supersede_node", "node:foundation", {"closing_event_id": "evt:" + "b" * 64})],
    )

    second = store.commit(supersede)

    assert store.snapshot(first.version_id)["nodes"]["node:foundation"]["state"] == "observed"
    assert store.snapshot(second.version_id)["nodes"]["node:foundation"]["state"] == "superseded"
    assert store.snapshot(second.version_id)["nodes"]["node:foundation"]["valid_to_event"] == "evt:" + "b" * 64


def test_unknown_operation_is_rejected_without_changing_head():
    store = DesignStateStore()
    invalid = proposal(store.head.version_id, [GraphOperation("delete_node", "node:a", {})])

    with pytest.raises(ValueError, match="unsupported graph operation"):
        store.commit(invalid)

    assert store.head.parent_version is None
    assert store.events == ()
