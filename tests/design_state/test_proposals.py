from types import MappingProxyType

import pytest

from gencore.design_state.proposals import GraphOperation, GraphProposal


def make_proposal(read_set=("node:b", "node:a"), write_set=("node:c",)):
    return GraphProposal.create(
        "run-1",
        "ver:1",
        read_set,
        write_set,
        [GraphOperation("set_node_state", "node:c", {"state": "verified"})],
        premise_event_ids=("evt:" + "b" * 64, "evt:" + "a" * 64),
        validation_plan=("schema", "write_set"),
    )


def test_proposal_hash_is_independent_of_set_input_order():
    first = make_proposal()
    second = make_proposal(read_set=("node:a", "node:b"))

    assert first.proposal_id == second.proposal_id
    assert first.read_set == ("node:a", "node:b")
    assert first.premise_event_ids == ("evt:" + "a" * 64, "evt:" + "b" * 64)


def test_operation_values_are_recursively_immutable():
    proposal = GraphProposal.create(
        "run-1",
        "ver:1",
        (),
        ("node:c",),
        [GraphOperation("add_node", "node:c", {"attributes": {"labels": ["基座"]}})],
        premise_event_ids=(),
        validation_plan=("schema",),
    )

    assert isinstance(proposal.operations[0].value, MappingProxyType)
    with pytest.raises(TypeError):
        proposal.operations[0].value["attributes"]["labels"] = ("设备",)
    assert proposal.to_dict()["operations"][0]["value"]["attributes"]["labels"] == ["基座"]

