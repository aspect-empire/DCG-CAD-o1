from gencore.design_state import DesignStateStore, GraphOperation, GraphProposal
from gencore.orchestration import AgentRole, default_role_policies
from gencore.orchestration.transaction_gateway import TransactionGateway


def proposal(base, operations, *, reads=(), writes=None, run_id="run-1"):
    return GraphProposal.create(
        run_id,
        base,
        reads,
        writes or tuple(operation.target for operation in operations),
        operations,
        (),
        ("schema", "role", "state_transition", "write_set"),
    )


def add_parameter(uid, state="unknown"):
    return GraphOperation(
        "add_node",
        uid,
        {
            "uid": uid,
            "view": "parameter_rule",
            "node_type": "ParameterValue",
            "state": state,
            "attributes": {"missing_inputs": ["value"]} if state == "unknown" else {},
        },
    )


def set_state(uid, state):
    return GraphOperation("set_node_state", uid, {"state": state})


def seeded_store():
    store = DesignStateStore()
    store.commit(
        proposal(
            store.head.version_id,
            (add_parameter("node:a"), add_parameter("node:b")),
        )
    )
    return store


def test_parameter_role_cannot_create_validation_node():
    store = DesignStateStore()
    head_before = store.head.version_id
    operation = GraphOperation(
        "add_node",
        "node:validation",
        {
            "uid": "node:validation",
            "view": "result_evidence",
            "node_type": "Validation",
            "state": "observed",
        },
    )

    result = TransactionGateway(store, default_role_policies()).submit(
        AgentRole.SOLUTION_PARAMETER,
        proposal(store.head.version_id, (operation,)),
    )

    assert result.status == "rejected"
    assert "cannot create Validation" in result.reason
    assert store.head.version_id == head_before
    assert store.events[-1].kind == "proposal.rejected"


def test_stale_proposal_rebases_when_reads_and_writes_are_unchanged():
    store = seeded_store()
    old_base = store.head.version_id
    store.commit(proposal(old_base, (set_state("node:b", "rejected"),)))
    stale = proposal(
        old_base,
        (set_state("node:a", "derived"),),
        reads=("node:a",),
    )

    result = TransactionGateway(store, default_role_policies()).submit(
        AgentRole.SOLUTION_PARAMETER,
        stale,
    )

    assert result.status == "committed"
    assert result.rebased_from == old_base
    assert result.proposal_id != stale.proposal_id
    assert store.snapshot()["nodes"]["node:a"]["state"] == "derived"


def test_stale_read_is_rejected_without_changing_head():
    store = seeded_store()
    old_base = store.head.version_id
    store.commit(proposal(old_base, (set_state("node:a", "derived"),)))
    current = store.head.version_id
    stale = proposal(
        old_base,
        (set_state("node:b", "derived"),),
        reads=("node:a",),
    )

    result = TransactionGateway(store, default_role_policies()).submit(
        AgentRole.SOLUTION_PARAMETER,
        stale,
    )

    assert result.status == "rejected"
    assert "stale reads" in result.reason
    assert store.head.version_id == current


def test_verified_node_cannot_regress_to_candidate():
    store = seeded_store()
    store.commit(proposal(store.head.version_id, (set_state("node:a", "verified"),)))
    current = store.head.version_id

    result = TransactionGateway(store, default_role_policies()).submit(
        AgentRole.SOLUTION_PARAMETER,
        proposal(current, (set_state("node:a", "candidate"),)),
    )

    assert result.status == "rejected"
    assert "illegal state transition" in result.reason
    assert store.head.version_id == current
