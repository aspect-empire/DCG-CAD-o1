import json
from decimal import Decimal
from pathlib import Path

import pytest

from gencore.case_matching import FoundationCaseMatcher
from gencore.resources import case_matching_weights_path, case_registry_path


@pytest.fixture
def template_registry():
    return json.loads(
        case_registry_path().read_text(
            encoding="utf-8"
        )
    )


@pytest.fixture
def weights():
    return json.loads(
        case_matching_weights_path().read_text(
            encoding="utf-8"
        )
    )


def query(**overrides):
    payload = {
        "equipment_type": "pump",
        "mount_surface": "deck",
        "dry_mass_kg": "900",
        "installation_length_mm": "800",
        "installation_width_mm": "600",
        "required_features": ["holes", "gussets"],
    }
    payload.update(overrides)
    return payload


def test_hard_incompatible_mount_is_filtered(template_registry, weights):
    result = FoundationCaseMatcher(template_registry, weights).match(query())

    assert all(item.template_id != "wall-mounted" for item in result.candidates)
    assert {
        (item["template_id"], item["field"], item["reason"])
        for item in result.filtered
    } >= {("wall-mounted", "mount_surface", "hard_conflict")}


def test_same_input_produces_same_top_k_and_hash(template_registry, weights):
    matcher = FoundationCaseMatcher(template_registry, weights)

    first = matcher.match(query(), top_k=2)
    second = matcher.match(query(), top_k=2)

    assert first == second
    assert first.content_hash == second.content_hash
    assert len(first.candidates) == 2
    assert first.candidates[0].dimension_scores
    assert all(
        isinstance(score, Decimal)
        for score in first.candidates[0].dimension_scores.values()
    )


def test_unknown_query_dimension_is_not_scored_as_zero(template_registry, weights):
    matcher = FoundationCaseMatcher(template_registry, weights)
    full = matcher.match(query())
    partial = matcher.match(
        query(installation_width_mm=None, required_features=None)
    )

    full_top = full.candidates[0]
    partial_top = partial.candidates[0]
    assert "installation_width_mm" not in partial_top.dimension_scores
    assert "required_features" not in partial_top.dimension_scores
    assert partial_top.evidence_coverage < full_top.evidence_coverage
    assert partial_top.total_score > Decimal("0")


def test_result_explains_parameter_reuse_and_recomputation(
    template_registry, weights
):
    result = FoundationCaseMatcher(template_registry, weights).match(query())

    top = result.candidates[0]
    assert top.reusable_parameters
    assert top.recompute_parameters
    assert top.artifact_refs
    assert top.total_score == max(item.total_score for item in result.candidates)


def test_invalid_numeric_input_is_rejected(template_registry, weights):
    matcher = FoundationCaseMatcher(template_registry, weights)

    with pytest.raises(ValueError, match="dry_mass_kg"):
        matcher.match(query(dry_mass_kg="unknown"))
