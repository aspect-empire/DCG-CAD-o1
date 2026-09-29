import pytest

from gencore.design_state.proposals import GraphOperation, GraphProposal
from gencore.design_state.validator import ProposalConflict, ProposalValidator


def proposal(base, writes=("node:a",), target="node:a"):
    return GraphProposal.create(
        "run-1",
        base,
        (),
        writes,
        [GraphOperation("set_node_state", target, {"state": "verified"})],
        premise_event_ids=("evt:" + "a" * 64,),
        validation_plan=("schema", "write_set"),
    )


def test_overlapping_write_after_base_version_is_rejected():
    validator = ProposalValidator(current_version="ver:2", changed_since_base={"node:a"})

    with pytest.raises(ProposalConflict, match="node:a"):
        validator.validate(proposal("ver:1"))


def test_non_overlapping_stale_proposal_can_rebase():
    validator = ProposalValidator(current_version="ver:2", changed_since_base={"node:b"})

    result = validator.validate(proposal("ver:1"))

    assert result.rebased_to == "ver:2"
    assert result.proposal_id.startswith("proposal:")


def test_operation_target_must_be_declared_in_write_set():
    validator = ProposalValidator(current_version="ver:1", changed_since_base=set())

    with pytest.raises(ValueError, match="missing from write_set"):
        validator.validate(proposal("ver:1", writes=("node:b",), target="node:a"))
