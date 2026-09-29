"""Normalized tool wrapper for deterministic foundation case matching."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from gencore.case_matching import FoundationCaseMatcher
from gencore.design_state.adapters.case_matching import CaseMatchingAdapter
from gencore.resources import case_matching_weights_path, case_registry_path
from gencore.tool_registry import ToolSpec


OBJECT_SCHEMA = {"type": "object"}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def match_foundation_cases(payload: Mapping[str, Any]) -> dict[str, Any]:
    for required in ("run_id", "base_version"):
        if not payload.get(required):
            raise ValueError(f"{required} is required")

    registry_path = case_registry_path()
    weights_path = case_matching_weights_path()
    registry = _read_json(registry_path)
    matcher = FoundationCaseMatcher(registry, _read_json(weights_path))
    top_k_value = payload.get("top_k")
    result = matcher.match(
        payload,
        top_k=int(top_k_value) if top_k_value is not None else None,
    )

    names = {
        str(item["template_id"]): str(item.get("name_zh", item["template_id"]))
        for item in registry["templates"]
    }
    candidates = []
    adapter_candidates = []
    for candidate in result.candidates:
        record = candidate.to_dict()
        record["state"] = "candidate"
        record["name"] = names[candidate.template_id]
        candidates.append(record)
        adapter_candidates.append(
            {
                "template_id": candidate.template_id,
                "name": names[candidate.template_id],
                "score": str(candidate.total_score),
                "locator": f"registry:templates/{candidate.template_id}",
                "features": {
                    "state": "candidate",
                    "evidence_coverage": str(candidate.evidence_coverage),
                    "reusable_parameters": list(candidate.reusable_parameters),
                    "recompute_parameters": list(candidate.recompute_parameters),
                },
            }
        )

    registry_digest = sha256(registry_path.read_bytes()).hexdigest()
    proposal = CaseMatchingAdapter().adapt(
        {
            "run_id": str(payload["run_id"]),
            "artifact_id": "registry:foundation-templates-v1",
            "media_type": "application/json",
            "sha256": registry_digest,
            "premise_event_ids": tuple(payload.get("premise_event_ids", ())),
            "candidates": adapter_candidates,
        },
        base_version=str(payload["base_version"]),
    )
    return {
        "status": result.status,
        "candidates": candidates,
        "filtered": [dict(item) for item in result.filtered],
        "content_hash": result.content_hash,
        "graph_proposal": proposal.to_dict(),
    }


def case_matching_tool_specs() -> list[ToolSpec]:
    return [
        ToolSpec(
            "foundation.case_matching.match",
            "Filter and rank foundation templates with deterministic evidence scores.",
            OBJECT_SCHEMA,
            OBJECT_SCHEMA,
            "read_only",
            "offline",
            lambda payload: match_foundation_cases(payload),
        )
    ]


__all__ = ["case_matching_tool_specs", "match_foundation_cases"]
