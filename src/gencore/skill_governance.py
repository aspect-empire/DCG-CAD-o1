"""Deterministic candidate-Skill governance with mandatory human boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Any


@dataclass(frozen=True)
class CandidateEvidence:
    candidate_id: str
    task_id: str
    successful_recovery: bool
    held_out_regression_pass: bool
    safety_regression_count: int
    event_id: str


@dataclass(frozen=True)
class PromotionDecision:
    candidate_id: str
    action: str
    reasons: tuple[str, ...]
    metrics: Mapping[str, Any]
    premise_event_ids: tuple[str, ...]
    writes_formal_rules: bool = False


@dataclass(frozen=True)
class SupersessionOperation:
    old_version: str
    new_version: str
    approved_by: str
    relation: str = "SUPERSEDES"


class SkillGovernance:
    def aggregate(self, evidence: Iterable[CandidateEvidence]) -> dict[str, Any]:
        items = list(evidence)
        if not items:
            raise ValueError("candidate evidence is required")
        candidates = {item.candidate_id for item in items}
        if len(candidates) != 1:
            raise ValueError("evidence for exactly one candidate is required")
        task_ids = {item.task_id for item in items}
        recovered_tasks = {item.task_id for item in items if item.successful_recovery}
        return {
            "candidate_id": items[0].candidate_id,
            "distinct_task_count": len(task_ids),
            "successful_recovery_rate": len(recovered_tasks) / len(task_ids),
            "held_out_regression_pass": all(item.held_out_regression_pass for item in items),
            "safety_regression_count": sum(item.safety_regression_count for item in items),
            "premise_event_ids": tuple(sorted({item.event_id for item in items})),
        }

    def evaluate(self, evidence: Iterable[CandidateEvidence]) -> PromotionDecision:
        metrics = self.aggregate(evidence)
        reasons: list[str] = []
        if metrics["distinct_task_count"] < 3:
            reasons.append("distinct_task_count_below_3")
        if metrics["successful_recovery_rate"] != 1.0:
            reasons.append("successful_recovery_rate_not_1")
        if not metrics["held_out_regression_pass"]:
            reasons.append("held_out_regression_failed")
        if metrics["safety_regression_count"] != 0:
            reasons.append("safety_regression_detected")
        if not reasons:
            action = "promote"
        elif reasons == ["distinct_task_count_below_3"]:
            action = "hold"
        else:
            action = "reject"
        public_metrics = {key: value for key, value in metrics.items() if key not in {"candidate_id", "premise_event_ids"}}
        return PromotionDecision(metrics["candidate_id"], action, tuple(reasons), public_metrics,
                                 metrics["premise_event_ids"], False)

    def supersede(self, old_version: str, new_version: str, *, approved_by: str) -> SupersessionOperation:
        if not old_version or not new_version or old_version == new_version or not approved_by:
            raise ValueError("distinct versions and explicit approver are required")
        return SupersessionOperation(old_version, new_version, approved_by)


PromotionPolicy = SkillGovernance
