from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..events import EngineeringEvent, EventSource, canonical_hash


class CadReportAdapter:
    producer = "cad_report_adapter"
    allowed_status = {"full_success", "degraded_success", "failed"}

    def adapt(self, report: Mapping[str, Any], *, run_id: str, path: str = "cad_report.json",
              sequence_start: int = 1, occurred_at: str = "1970-01-01T00:00:00Z") -> list[EngineeringEvent]:
        requested = report.get("requested_mode")
        actual = report.get("actual_mode")
        status = report.get("status")
        if status not in self.allowed_status:
            raise ValueError(f"invalid CAD status: {status!r}")
        if requested != actual and status == "full_success":
            raise ValueError("a fallback execution cannot be full_success")
        digest = canonical_hash(report)
        events: list[EngineeringEvent] = []

        def emit(kind: str, payload: Mapping[str, Any], locator: str) -> None:
            events.append(EngineeringEvent.create(
                run_id, sequence_start + len(events), kind, occurred_at, self.producer,
                EventSource(f"artifact:{digest}", path, locator, digest), payload))

        emit("execution.completed", {"requested_mode": requested, "actual_mode": actual, "status": status}, "$")
        if report.get("failure") or status == "failed":
            failure = dict(report.get("failure") or {})
            emit("failure.observed", {"raw_error_code": failure.get("code", failure.get("error_code", "CAD_FAILED")),
                                      "message": failure.get("message", ""), "status": "failed", "raw": failure}, "$.failure")
        if report.get("fallback") or (requested != actual and actual is not None):
            fallback = dict(report.get("fallback") or {"mode": actual})
            emit("fallback.activated", {"requested_mode": requested, "actual_mode": actual,
                                        "status": "degraded_success" if status == "degraded_success" else status,
                                        "raw": fallback}, "$.fallback")
        if report.get("artifact"):
            emit("artifact.produced", {"artifact": dict(report["artifact"]), "status": status}, "$.artifact")
        if report.get("validation"):
            validation = dict(report["validation"])
            emit("validation.completed", {"passed": bool(validation.get("passed")), "status": status,
                                           "raw": validation}, "$.validation")
        return events

    ingest = adapt


def adapt_cad_report(report: Mapping[str, Any], **kwargs: Any) -> list[EngineeringEvent]:
    return CadReportAdapter().adapt(report, **kwargs)
