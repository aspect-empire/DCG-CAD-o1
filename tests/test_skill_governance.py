from gencore.skill_governance import CandidateEvidence, SkillGovernance


def evidence(task="T1", success=True, held_out=True, safety=0):
    return CandidateEvidence("fallback-x", task, success, held_out, safety, f"evt:{task}")


def test_ex03_promotes_only_with_three_tasks_and_all_gates():
    gov = SkillGovernance()
    decision = gov.evaluate([evidence("T1"), evidence("T2"), evidence("T3")])
    assert decision.action == "promote"
    assert decision.metrics["distinct_task_count"] == 3
    assert decision.metrics["successful_recovery_rate"] == 1.0
    assert decision.writes_formal_rules is False


def test_ex03_removed_evidence_and_regression_failure_do_not_promote():
    gov = SkillGovernance()
    assert gov.evaluate([evidence("T1"), evidence("T2")]).action == "hold"
    assert gov.evaluate([evidence("T1"), evidence("T2"), evidence("T3", held_out=False)]).action == "reject"
    assert gov.evaluate([evidence("T1"), evidence("T2"), evidence("T3", safety=1)]).action == "reject"


def test_version_supersession_is_explicit():
    gov = SkillGovernance()
    operation = gov.supersede("skill:fallback-x@1", "skill:fallback-x@2", approved_by="human:alice")
    assert operation.relation == "SUPERSEDES"
    assert operation.old_version.endswith("@1") and operation.new_version.endswith("@2")
