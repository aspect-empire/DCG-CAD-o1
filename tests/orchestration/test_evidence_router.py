import pytest

from gencore.orchestration.evidence_router import EvidenceRouter
from gencore.orchestration.roles import AgentRole
from gencore.ports import ToolOutcome, ToolRequest
from gencore.tool_registry import build_default_registry


def test_matching_tool_proposal_is_routed_to_solution_role():
    base_version = "ver:" + "a" * 64
    payload = {
        "run_id": "route-1",
        "base_version": base_version,
        "equipment_type": "pump",
        "mount_surface": "deck",
        "dry_mass_kg": "900",
        "installation_length_mm": "800",
        "installation_width_mm": "600",
    }
    result = build_default_registry().invoke(
        "foundation.case_matching.match", payload
    )

    routed = EvidenceRouter.default().to_proposal(
        request=ToolRequest("foundation.case_matching.match", payload),
        outcome=ToolOutcome(
            "foundation.case_matching.match", "completed", result
        ),
        base_version=base_version,
    )

    assert routed.role is AgentRole.SOLUTION_PARAMETER
    assert routed.proposal.base_version == base_version


def test_unknown_tool_outcome_is_rejected():
    with pytest.raises(ValueError, match="unsupported evidence route"):
        EvidenceRouter.default().to_proposal(
            request=ToolRequest("unknown.tool", {}),
            outcome=ToolOutcome("unknown.tool", "completed", {"ok": True}),
            base_version="ver:base",
        )


def test_cad_approval_event_is_persisted_in_routed_graph_evidence():
    approval_id = "evt:" + "b" * 64
    routed = EvidenceRouter.default().to_proposal(
        request=ToolRequest(
            "geometry.cad.update_parameters",
            {"run_id": "run-approval"},
            operation_id="op-1",
            graph_version="ver:base",
        ),
        outcome=ToolOutcome(
            "geometry.cad.update_parameters",
            "completed",
            {"status": "completed", "run_id": "run-approval"},
            approval_event_id=approval_id,
        ),
        base_version="ver:base",
    )

    execution = next(
        item.value
        for item in routed.proposal.operations
        if item.value.get("node_type") == "Execution"
    )
    assert approval_id in routed.proposal.premise_event_ids
    assert execution["attributes"]["approval_event_id"] == approval_id
