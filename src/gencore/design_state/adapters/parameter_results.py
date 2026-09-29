"""Foundation calculation results to parameter and constraint graph records."""

from __future__ import annotations

from gencore.foundation_rules.calculator import CalculationResult

from ..ontology import ValueState, View
from ..proposals import GraphOperation, GraphProposal
from ..records import DesignNode, EvidenceRef
from .common import proposal_from_operations


class ParameterResultAdapter:
    def adapt(self, result: CalculationResult, *, run_id: str, base_version: str) -> GraphProposal:
        evidence = EvidenceRef(
            f"artifact:calculation:{result.content_hash}",
            "application/json",
            "$",
            result.content_hash,
        )
        summary = DesignNode.create(
            View.RESULT_EVIDENCE,
            "CalculationResult",
            f"{result.equipment_id}:{result.content_hash}",
            result.semantic_dict(),
            (evidence,),
            state=ValueState(result.status),
        )
        operations: list[GraphOperation] = [GraphOperation("add_node", summary.uid, summary.to_dict())]
        for view, node_type, decisions in (
            (View.PARAMETER_RULE, "ParameterValue", result.values),
            (View.GEOMETRY_SPATIAL, "Constraint", result.constraints),
        ):
            for name in sorted(decisions):
                decision = decisions[name]
                node = DesignNode.create(
                    view,
                    node_type,
                    f"{result.equipment_id}:{name}:{result.content_hash}",
                    {
                        "name": name,
                        **decision.to_dict(),
                        "calculation_hash": result.content_hash,
                        "intermediates": result.semantic_dict()["intermediates"],
                    },
                    (evidence,),
                    state=ValueState(decision.state),
                )
                operations.append(GraphOperation("add_node", node.uid, node.to_dict()))
        return proposal_from_operations(
            run_id=run_id,
            base_version=base_version,
            operations=operations,
            premise_event_ids=result.premise_event_ids,
        )
