import json
from pathlib import Path

import pytest

from gencore.orchestration import (
    AgentOutcome,
    DesignDecision,
    DesignExecutionPackage,
    Stage,
)


def package_values(**overrides):
    values = {
        "task_id": "GEN-001",
        "scenario_id": "SCN-01",
        "run_id": "run-001",
        "graph_version": "ver:" + "a" * 64,
        "stage": Stage.S0_INITIALIZE,
        "design_intent": {"object": "框架式基座"},
    }
    values.update(overrides)
    return values


def test_execution_package_round_trips_without_absolute_artifact_paths():
    package = DesignExecutionPackage.create(**package_values())

    restored = DesignExecutionPackage.from_dict(package.to_dict())

    assert restored == package
    assert package.package_id.startswith("dep:")
    assert package.parent_version is None


def test_absolute_artifact_locator_is_rejected():
    with pytest.raises(ValueError, match="relative"):
        DesignExecutionPackage.create(
            **package_values(
                artifact_refs=(
                    {"locator": "D:/outside/model.stl", "sha256": "b" * 64},
                )
            )
        )


def test_package_id_detects_changed_content():
    package = DesignExecutionPackage.create(**package_values())
    changed = package.to_dict()
    changed["design_intent"] = {"object": "板式基座"}

    with pytest.raises(ValueError, match="package_id"):
        DesignExecutionPackage.from_dict(changed)


def test_agent_outcome_cannot_claim_accepted():
    with pytest.raises(ValueError, match="DecisionEvaluator"):
        AgentOutcome(status="completed", requested_decision=DesignDecision.ACCEPTED)


def test_agent_outcome_preserves_structured_blocker_ids():
    outcome = AgentOutcome(
        status="blocked",
        missing_inputs=("[BLOCKER:input-risk:abc] revise parameters",),
        blocker_ids=("input-risk:abc",),
    )

    assert outcome.blocker_ids == ("input-risk:abc",)


def test_execution_package_schema_declares_closed_required_contract():
    schema = json.loads(
        Path("schemas/design-execution-package.schema.json").read_text(encoding="utf-8")
    )

    assert schema["additionalProperties"] is False
    assert {
        "package_id",
        "task_id",
        "scenario_id",
        "run_id",
        "graph_version",
        "stage",
        "read_set",
        "write_set",
        "artifact_refs",
        "validation_evidence",
        "current_decision",
    } <= set(schema["required"])
