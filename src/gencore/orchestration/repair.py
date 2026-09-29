"""Deterministic ranking and rejection of local engineering repairs."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable


ACTION_PRECEDENCE = (
    "parameter_update",
    "reference_relocation",
    "local_feature",
    "local_rebuild",
    "full_rebuild",
    "human_handoff",
)


@dataclass(frozen=True)
class RepairAction:
    action_id: str
    action_type: str
    targets: tuple[str, ...]
    rebuild_scope: Decimal
    execution_cost: Decimal
    risk: Decimal
    revalidations: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.action_id:
            raise ValueError("repair action_id must be non-empty")
        if self.action_type not in ACTION_PRECEDENCE:
            raise ValueError(f"unsupported repair action type: {self.action_type}")
        if not self.targets:
            raise ValueError("repair action requires at least one target")
        for field in ("rebuild_scope", "execution_cost", "risk"):
            value = Decimal(getattr(self, field))
            if value < 0:
                raise ValueError(f"{field} cannot be negative")
            object.__setattr__(self, field, value)
        object.__setattr__(self, "targets", tuple(str(item) for item in self.targets))
        object.__setattr__(
            self, "revalidations", tuple(sorted({str(item) for item in self.revalidations}))
        )


@dataclass(frozen=True)
class RepairPolicy:
    rebuild_weight: Decimal = Decimal("1")
    execution_weight: Decimal = Decimal("1")
    risk_weight: Decimal = Decimal("1")

    def __post_init__(self) -> None:
        for field in ("rebuild_weight", "execution_weight", "risk_weight"):
            value = Decimal(getattr(self, field))
            if value < 0:
                raise ValueError(f"{field} cannot be negative")
            object.__setattr__(self, field, value)


@dataclass(frozen=True)
class RankedRepair:
    action: RepairAction
    score: Decimal


@dataclass(frozen=True)
class RejectedRepair:
    action_id: str
    reason: str


@dataclass(frozen=True)
class RepairPlan:
    ranked: tuple[RankedRepair, ...]
    rejected: tuple[RejectedRepair, ...]


class RepairPlanner:
    def __init__(self, policy: RepairPolicy | None = None) -> None:
        self.policy = policy or RepairPolicy()

    def rank(
        self,
        actions: Iterable[RepairAction],
        *,
        protected: set[str] | frozenset[str] = frozenset(),
        required_revalidations: set[str] | frozenset[str] = frozenset(),
    ) -> RepairPlan:
        protected_set = set(protected)
        required = set(required_revalidations)
        ranked: list[RankedRepair] = []
        rejected: list[RejectedRepair] = []
        precedence = {name: index for index, name in enumerate(ACTION_PRECEDENCE)}

        for action in actions:
            if protected_set.intersection(action.targets):
                rejected.append(
                    RejectedRepair(action.action_id, "touches_protected_node")
                )
                continue
            if not required.issubset(action.revalidations):
                rejected.append(
                    RejectedRepair(
                        action.action_id, "missing_required_revalidation"
                    )
                )
                continue
            score = (
                self.policy.rebuild_weight * action.rebuild_scope
                + self.policy.execution_weight * action.execution_cost
                + self.policy.risk_weight * action.risk
            )
            ranked.append(RankedRepair(action, score))

        ranked.sort(
            key=lambda item: (
                item.score,
                precedence[item.action.action_type],
                item.action.action_id,
            )
        )
        rejected.sort(key=lambda item: (item.action_id, item.reason))
        return RepairPlan(tuple(ranked), tuple(rejected))


__all__ = [
    "ACTION_PRECEDENCE",
    "RankedRepair",
    "RejectedRepair",
    "RepairAction",
    "RepairPlan",
    "RepairPlanner",
    "RepairPolicy",
]
