from gencore.design_state import DesignStateStore, GraphOperation, GraphProposal
from gencore.design_state.inference import build_invalidation_proposal


def seed_store():
    store = DesignStateStore()
    operations = [
        GraphOperation("add_node", uid, {"uid": uid, "state": "derived", "evidence": []})
        for uid in ("load", "band", "panel_t", "paint")
    ]
    proposal = GraphProposal.create(
        "run-1",
        store.head.version_id,
        (),
        tuple(operation.target for operation in operations),
        operations,
        (),
        ("schema", "write_set"),
    )
    store.commit(proposal)
    return store


def test_invalidation_proposal_updates_only_downstream_and_preserves_reason():
    store = seed_store()
    event_id = "evt:" + "c" * 64
    proposal = build_invalidation_proposal(
        run_id="run-1",
        base_version=store.head.version_id,
        dependencies={"load": {"band"}, "band": {"panel_t"}, "paint": set()},
        changed_uids={"load"},
        premise_event_ids=(event_id,),
    )

    assert proposal.write_set == ("band", "panel_t")
    store.commit(proposal)
    snapshot = store.snapshot()
    assert snapshot["nodes"]["band"]["state"] == "unknown"
    assert snapshot["nodes"]["band"]["invalidated_by"] == [event_id]
    assert snapshot["nodes"]["load"]["state"] == "derived"
    assert snapshot["nodes"]["paint"]["state"] == "derived"
