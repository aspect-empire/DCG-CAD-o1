"""Approval port for risk-gated engineering actions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol


@dataclass(frozen=True)
class ApprovalRequest:
    operation_id: str
    tool_name: str
    graph_version: str
    risk_level: str
    run_id: str | None = None


@dataclass(frozen=True)
class ApprovalDecision:
    approved: bool
    mode: str
    event_id: str | None = None
    reason: str | None = None


class ApprovalGateway(Protocol):
    def request(self, request: ApprovalRequest) -> ApprovalDecision: ...


class InMemoryApprovalGateway:
    def __init__(
        self,
        decisions: Mapping[str, ApprovalDecision] | None = None,
    ) -> None:
        self.decisions = dict(decisions or {})
        self.requests: list[ApprovalRequest] = []

    def request(self, request: ApprovalRequest) -> ApprovalDecision:
        self.requests.append(request)
        return self.decisions.get(
            request.operation_id,
            ApprovalDecision(False, "deny", reason="approval was not recorded"),
        )


class AllowReadOnlyApproval:
    def request(self, request: ApprovalRequest) -> ApprovalDecision:
        if request.risk_level == "external_cad":
            return ApprovalDecision(False, "deny", reason="external CAD approval is required")
        return ApprovalDecision(True, "not_required")


__all__ = [
    "AllowReadOnlyApproval",
    "ApprovalDecision",
    "ApprovalGateway",
    "ApprovalRequest",
    "InMemoryApprovalGateway",
]
