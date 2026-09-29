from decimal import Decimal

from gencore.orchestration.repair import (
    RepairAction,
    RepairPlanner,
    RepairPolicy,
)


def action(
    action_id,
    action_type,
    *,
    targets=("feature:hole",),
    rebuild_scope="1",
    execution_cost="1",
    risk="1",
    revalidations=("interference",),
):
    return RepairAction(
        action_id=action_id,
        action_type=action_type,
        targets=targets,
        rebuild_scope=Decimal(rebuild_scope),
        execution_cost=Decimal(execution_cost),
        risk=Decimal(risk),
        revalidations=revalidations,
    )


def test_repair_ranking_uses_weighted_cost_and_stable_precedence():
    planner = RepairPlanner(
        RepairPolicy(
            rebuild_weight=Decimal("2"),
            execution_weight=Decimal("1"),
            risk_weight=Decimal("3"),
        )
    )
    result = planner.rank(
        (
            action("full", "full_rebuild", rebuild_scope="4", risk="2"),
            action("parameter", "parameter_update"),
            action("reference", "reference_relocation"),
        ),
        required_revalidations={"interference"},
    )

    assert tuple(item.action.action_id for item in result.ranked) == (
        "parameter",
        "reference",
        "full",
    )
    assert result.ranked[0].score == Decimal("6")


def test_equal_scores_follow_action_precedence_then_id():
    planner = RepairPlanner()
    result = planner.rank(
        (
            action("local-z", "local_feature"),
            action("reference", "reference_relocation"),
            action("parameter-b", "parameter_update"),
            action("parameter-a", "parameter_update"),
        ),
        required_revalidations={"interference"},
    )

    assert tuple(item.action.action_id for item in result.ranked) == (
        "parameter-a",
        "parameter-b",
        "reference",
        "local-z",
    )


def test_actions_touching_protected_nodes_or_omitting_revalidation_are_rejected():
    planner = RepairPlanner()
    result = planner.rank(
        (
            action("protected", "parameter_update", targets=("feature:verified",)),
            action("missing-validation", "local_feature", revalidations=()),
            action("valid", "local_rebuild"),
        ),
        protected={"feature:verified"},
        required_revalidations={"interference"},
    )

    assert tuple(item.action.action_id for item in result.ranked) == ("valid",)
    assert {(item.action_id, item.reason) for item in result.rejected} == {
        ("protected", "touches_protected_node"),
        ("missing-validation", "missing_required_revalidation"),
    }
