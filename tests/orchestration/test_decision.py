from gencore.orchestration import DesignDecision
from gencore.orchestration.decision import DecisionEvaluator


def accepted_payload(**overrides):
    payload = {
        "proven_unsatisfiable": False,
        "critical_evidence_missing": False,
        "template_insufficient": False,
        "reference_ambiguous": False,
        "budget_exhausted": False,
        "cad": {"openable": True, "updateable": True, "exportable": True},
        "hard_constraints": [{"constraint_id": "c:1", "status": "passed"}],
        "critical_unknowns": [],
        "conflicts": [],
        "validation_coverage": 1.0,
        "evidence_refs": ["evidence:cad", "evidence:constraint"],
    }
    payload.update(overrides)
    return payload


def test_artifact_presence_alone_never_accepts():
    result = DecisionEvaluator().evaluate(
        {
            "artifacts": [{"media_type": "model/stl", "verified": True}],
            "hard_constraints": [],
            "critical_unknowns": ["constraint:clearance"],
            "conflicts": [],
            "validation_coverage": 1.0,
        }
    )

    assert result.decision is DesignDecision.HUMAN_REQUIRED
    assert "critical_evidence" in result.failed_gates


def test_accept_requires_cad_and_all_engineering_gates():
    result = DecisionEvaluator().evaluate(accepted_payload())

    assert result.decision is DesignDecision.ACCEPTED
    assert result.failed_gates == ()
    assert {"cad", "hard_constraints", "validation"} <= set(result.passed_gates)


def test_proven_unsatisfiable_has_priority_over_missing_evidence():
    result = DecisionEvaluator().evaluate(
        accepted_payload(
            proven_unsatisfiable=True,
            critical_evidence_missing=True,
        )
    )

    assert result.decision is DesignDecision.REJECTED
    assert result.failed_gates == ("satisfiability",)


def test_ambiguity_requires_human_before_budget_abstention():
    result = DecisionEvaluator().evaluate(
        accepted_payload(reference_ambiguous=True, budget_exhausted=True)
    )

    assert result.decision is DesignDecision.HUMAN_REQUIRED
    assert "reference_ambiguity" in result.failed_gates


def test_budget_exhaustion_without_proof_abstains():
    result = DecisionEvaluator().evaluate(accepted_payload(budget_exhausted=True))

    assert result.decision is DesignDecision.ABSTAINED
    assert result.failed_gates == ("budget",)


def test_incomplete_cad_or_validation_remains_running():
    no_export = DecisionEvaluator().evaluate(
        accepted_payload(cad={"openable": True, "updateable": True, "exportable": False})
    )
    failed_constraint = DecisionEvaluator().evaluate(
        accepted_payload(
            hard_constraints=[{"constraint_id": "c:1", "status": "failed"}]
        )
    )

    assert no_export.decision is DesignDecision.RUNNING
    assert "cad_exportable" in no_export.failed_gates
    assert failed_constraint.decision is DesignDecision.RUNNING
    assert "hard_constraints" in failed_constraint.failed_gates


def test_validation_threshold_comes_from_policy(tmp_path):
    policy = tmp_path / "policy.json"
    policy.write_text(
        '{"minimum_validation_coverage": 0.75, '
        '"required_cad_evidence": ["openable", "updateable", "exportable"]}',
        encoding="utf-8",
    )
    evaluator = DecisionEvaluator(policy_path=policy)

    accepted = evaluator.evaluate(accepted_payload(validation_coverage=0.75))
    running = evaluator.evaluate(accepted_payload(validation_coverage=0.74))

    assert accepted.decision is DesignDecision.ACCEPTED
    assert running.decision is DesignDecision.RUNNING
