import pytest

from gencore.foundation_rules.schema import RuleClause


def test_deterministic_rule_requires_an_expression():
    with pytest.raises(ValueError, match="expression"):
        RuleClause("R1", "deterministic", "shall", "doc", "paragraph:1", (), None)


def test_rule_requires_supported_classification_and_normative_strength():
    with pytest.raises(ValueError, match="classification"):
        RuleClause("R1", "guess", "shall", "doc", "paragraph:1", (), {"op": "const", "value": 1})
    with pytest.raises(ValueError, match="normative_strength"):
        RuleClause("R2", "advisory", "always", "doc", "paragraph:2", (), None)


def test_rule_serialization_is_stable_and_uses_lists_at_json_boundary():
    rule = RuleClause(
        "D02-P34",
        "deterministic",
        "shall",
        "foundation-rule-doc-02",
        "paragraph:34",
        ("moving_equipment",),
        {"op": "increase_grade", "steps": "1"},
    )

    assert rule.to_dict()["inputs"] == ["moving_equipment"]
    assert rule.content_hash == rule.recompute_hash()
