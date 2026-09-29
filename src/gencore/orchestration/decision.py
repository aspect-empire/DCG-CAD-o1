"""Ordered, auditable terminal decision gates for engineering design runs."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping

from .contracts import DesignDecision


@dataclass(frozen=True)
class DecisionResult:
    decision: DesignDecision
    passed_gates: tuple[str, ...]
    failed_gates: tuple[str, ...]
    evidence_refs: tuple[str, ...]


class DecisionEvaluator:
    """Evaluate terminal state without allowing an agent to self-approve."""

    def __init__(self, *, policy_path: str | Path | None = None) -> None:
        path = (
            Path(policy_path)
            if policy_path is not None
            else Path(__file__).resolve().parents[3]
            / "config"
            / "orchestration"
            / "termination_policy.json"
        )
        self._policy = json.loads(path.read_text(encoding="utf-8"))
        self._minimum_coverage = float(
            self._policy["minimum_validation_coverage"]
        )
        self._required_cad = tuple(self._policy["required_cad_evidence"])
        if not 0.0 <= self._minimum_coverage <= 1.0:
            raise ValueError("minimum_validation_coverage must be between 0 and 1")
        if not self._required_cad:
            raise ValueError("required_cad_evidence cannot be empty")

    def evaluate(self, state: Mapping[str, Any]) -> DecisionResult:
        evidence_refs = tuple(
            sorted({str(item) for item in state.get("evidence_refs", ())})
        )

        if bool(state.get("proven_unsatisfiable", False)):
            return DecisionResult(
                DesignDecision.REJECTED,
                (),
                ("satisfiability",),
                evidence_refs,
            )

        human_failures = self._human_required_failures(state, evidence_refs)
        if human_failures:
            return DecisionResult(
                DesignDecision.HUMAN_REQUIRED,
                ("satisfiability",),
                human_failures,
                evidence_refs,
            )

        if bool(state.get("budget_exhausted", False)):
            return DecisionResult(
                DesignDecision.ABSTAINED,
                ("satisfiability", "critical_evidence"),
                ("budget",),
                evidence_refs,
            )

        cad_failures = self._cad_failures(state)
        if cad_failures:
            return DecisionResult(
                DesignDecision.RUNNING,
                ("satisfiability", "critical_evidence", "budget"),
                cad_failures,
                evidence_refs,
            )

        engineering_failures = self._engineering_failures(state)
        if engineering_failures:
            return DecisionResult(
                DesignDecision.RUNNING,
                (
                    "satisfiability",
                    "critical_evidence",
                    "budget",
                    "cad",
                ),
                engineering_failures,
                evidence_refs,
            )

        return DecisionResult(
            DesignDecision.ACCEPTED,
            (
                "satisfiability",
                "critical_evidence",
                "budget",
                "cad",
                "hard_constraints",
                "critical_unknowns",
                "conflicts",
                "validation",
            ),
            (),
            evidence_refs,
        )

    @staticmethod
    def _human_required_failures(
        state: Mapping[str, Any], evidence_refs: tuple[str, ...]
    ) -> tuple[str, ...]:
        failed: list[str] = []
        hard_constraints = state.get("hard_constraints")
        if (
            bool(state.get("critical_evidence_missing", False))
            or not evidence_refs
            or hard_constraints is None
            or len(hard_constraints) == 0
        ):
            failed.append("critical_evidence")
        if bool(state.get("template_insufficient", False)):
            failed.append("template_sufficiency")
        if bool(state.get("reference_ambiguous", False)):
            failed.append("reference_ambiguity")
        return tuple(failed)

    def _cad_failures(self, state: Mapping[str, Any]) -> tuple[str, ...]:
        cad = state.get("cad")
        if not isinstance(cad, Mapping):
            return tuple(f"cad_{name}" for name in self._required_cad)
        return tuple(
            f"cad_{name}" for name in self._required_cad if cad.get(name) is not True
        )

    def _engineering_failures(
        self, state: Mapping[str, Any]
    ) -> tuple[str, ...]:
        failures: list[str] = []
        constraints = state.get("hard_constraints", ())
        if any(
            not isinstance(item, Mapping) or item.get("status") != "passed"
            for item in constraints
        ):
            failures.append("hard_constraints")
        if state.get("critical_unknowns"):
            failures.append("critical_unknowns")
        if state.get("conflicts"):
            failures.append("conflicts")
        try:
            coverage = float(state.get("validation_coverage", 0.0))
        except (TypeError, ValueError):
            coverage = 0.0
        if coverage < self._minimum_coverage:
            failures.append("validation")
        return tuple(failures)


__all__ = ["DecisionEvaluator", "DecisionResult"]
