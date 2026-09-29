"""Independent validation aggregation and graph-proposal conversion."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from gencore.design_state.adapters.catia_pipeline import CatiaPipelineAdapter
from gencore.design_state.adapters.interference import InterferenceAdapter
from gencore.design_state.dependencies import affected_closure

from .contracts import ValidationCheck, ValidationFinding, ValidationResult


REQUIRED_CHECK_KINDS = frozenset(
    {
        "model_exists",
        "model_openable",
        "model_updateable",
        "model_exportable",
        "topology_validity",
        "feature_validity",
        "parameter_compliance",
        "rule_compliance",
        "interface_reference",
        "installation_reference",
        "hole_constraints",
        "gusset_constraints",
        "envelope",
        "clearance",
        "accessibility",
        "interference",
        "critical_unknown_scan",
        "conflict_scan",
        "provenance_coverage",
        "evidence_coverage",
    }
)


class ValidationService:
    def evaluate(
        self,
        *,
        plan: Mapping[str, Any],
        tool_results: Sequence[Mapping[str, Any]],
        graph_snapshot: Mapping[str, Any],
    ) -> ValidationResult:
        del graph_snapshot  # snapshot remains an explicit boundary for future checkers
        checks = tuple(
            ValidationCheck.from_dict(item) for item in plan.get("checks", ())
        )
        for check in checks:
            if check.kind not in REQUIRED_CHECK_KINDS:
                raise ValueError(f"unsupported validation check kind: {check.kind}")

        by_check: dict[str, list[Mapping[str, Any]]] = {}
        for result in tool_results:
            check_id = result.get("check_id")
            if check_id:
                by_check.setdefault(str(check_id), []).append(result)

        findings: list[ValidationFinding] = []
        missing: list[str] = []
        affected: set[str] = set()
        evidence: set[str] = set()
        proposals: list[Mapping[str, Any]] = []
        passed_required = 0
        required_count = sum(1 for item in checks if item.required)

        for check in checks:
            result = self._select_result(by_check.get(check.check_id, ()))
            finding = self._finding(check, result)
            findings.append(finding)
            affected.update(finding.affected_uids)
            evidence.update(finding.evidence_refs)
            if check.required:
                if finding.state == "passed":
                    passed_required += 1
                elif finding.state == "unknown":
                    missing.append(check.kind)
            if result is not None:
                proposal = self._proposal(plan, result)
                if proposal is not None:
                    proposals.append(proposal)

        if any(
            item.required and finding.state == "failed"
            for item, finding in zip(checks, findings, strict=True)
        ):
            status = "failed"
        elif any(
            item.required and finding.state != "passed"
            for item, finding in zip(checks, findings, strict=True)
        ):
            status = "incomplete"
        else:
            status = "passed"
        coverage = passed_required / required_count if required_count else 1.0
        return ValidationResult(
            status=status,
            findings=tuple(findings),
            missing_checks=tuple(sorted(set(missing))),
            affected_uids=tuple(sorted(affected)),
            evidence_refs=tuple(sorted(evidence)),
            coverage=coverage,
            graph_proposals=tuple(proposals),
        )

    @staticmethod
    def _select_result(
        results: Sequence[Mapping[str, Any]],
    ) -> Mapping[str, Any] | None:
        if not results:
            return None
        ordered = sorted(
            results,
            key=lambda item: (
                {"failed": 0, "unknown": 1, "passed": 2, "completed": 2}.get(
                    str(item.get("status")), 1
                ),
                str(item.get("tool_id", "")),
            ),
        )
        return ordered[0]

    @staticmethod
    def _finding(
        check: ValidationCheck, result: Mapping[str, Any] | None
    ) -> ValidationFinding:
        if result is None:
            return ValidationFinding(
                check.check_id,
                check.kind,
                "error" if check.required else "warning",
                "unknown",
                (),
                (),
                None,
                None,
                "collect_independent_evidence",
            )
        evidence_refs = tuple(
            sorted({str(item) for item in result.get("evidence_refs", ())})
        )
        raw_status = str(result.get("status", "unknown"))
        if raw_status in {"passed", "completed", "success"} and evidence_refs:
            state = "passed"
            recommended = "none"
        elif raw_status in {"failed", "error"}:
            state = "failed"
            recommended = "repair_and_revalidate"
        else:
            state = "unknown"
            recommended = "collect_independent_evidence"

        dependencies = {
            str(key): {str(item) for item in values}
            for key, values in result.get("dependencies", {}).items()
        }
        starts = {str(item) for item in result.get("changed_uids", ())}
        affected = (
            affected_closure(dependencies, starts) if starts else set()
        )
        return ValidationFinding(
            check_id=check.check_id,
            kind=check.kind,
            severity="error" if check.required else "warning",
            state=state,
            affected_uids=tuple(sorted(affected)),
            evidence_refs=evidence_refs,
            tool_id=(
                str(result["tool_id"]) if result.get("tool_id") is not None else None
            ),
            model_version=(
                str(result["model_version"])
                if result.get("model_version") is not None
                else None
            ),
            recommended_action=recommended,
        )

    @staticmethod
    def _proposal(
        plan: Mapping[str, Any], result: Mapping[str, Any]
    ) -> Mapping[str, Any] | None:
        base_version = str(plan.get("base_version", ""))
        if not base_version:
            return None
        if isinstance(result.get("catia_manifest"), Mapping):
            return CatiaPipelineAdapter().adapt(
                result["catia_manifest"], base_version=base_version
            ).to_dict()
        if isinstance(result.get("interference_report"), Mapping):
            return InterferenceAdapter().adapt(
                result["interference_report"], base_version=base_version
            ).to_dict()
        return None


__all__ = ["REQUIRED_CHECK_KINDS", "ValidationService"]
