"""Case-matching candidate records to typed graph proposals."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..ontology import View
from ..proposals import GraphOperation, GraphProposal
from ..records import DesignNode, EvidenceRef
from .common import proposal_from_operations


class CaseMatchingAdapter:
    def adapt(self, payload: Mapping[str, Any], *, base_version: str) -> GraphProposal:
        operations: list[GraphOperation] = []
        candidates = sorted(
            payload.get("candidates", ()),
            key=lambda item: (-float(item["score"]), str(item["template_id"])),
        )
        for rank, candidate in enumerate(candidates, 1):
            evidence = EvidenceRef(
                str(payload["artifact_id"]),
                str(payload.get("media_type", "application/json")),
                str(candidate["locator"]),
                str(payload["sha256"]),
            )
            node = DesignNode.create(
                View.PRODUCT_FUNCTION,
                "CandidateTemplate",
                str(candidate["template_id"]),
                {
                    "template_id": candidate["template_id"],
                    "name": candidate.get("name", candidate["template_id"]),
                    "rank": rank,
                    "score": candidate["score"],
                    "features": candidate.get("features", {}),
                },
                (evidence,),
            )
            operations.append(GraphOperation("add_node", node.uid, node.to_dict()))
        return proposal_from_operations(
            run_id=str(payload["run_id"]),
            base_version=base_version,
            operations=operations,
            premise_event_ids=tuple(payload.get("premise_event_ids", ())),
        )
