from gencore import DesignStateStore, GraphProposal, ProposalValidator, ValueState


def test_public_design_state_api_is_available():
    assert DesignStateStore().head.status == "committed"
    assert GraphProposal.__name__ == "GraphProposal"
    assert ProposalValidator.__name__ == "ProposalValidator"
    assert ValueState.CONFLICTED.value == "conflicted"
