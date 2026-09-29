import json
from pathlib import Path

import pytest

from gencore.orchestration import Stage
from gencore.orchestration.state_machine import StageMachine


def test_s4_failure_enters_s5_and_s5_can_return_to_s2():
    machine = StageMachine.default()

    assert (
        machine.transition(Stage.S4_VALIDATE, "validation_failed")
        is Stage.S5_REPAIR_OR_HANDOFF
    )
    assert (
        machine.transition(Stage.S5_REPAIR_OR_HANDOFF, "replan_geometry")
        is Stage.S2_PLAN_GEOMETRY
    )


def test_nominal_generation_path_is_explicit():
    machine = StageMachine.default()
    current = Stage.S0_INITIALIZE
    for event in (
        "evidence_ready",
        "constraints_ready",
        "plan_ready",
        "cad_completed",
    ):
        current = machine.transition(current, event)

    assert current is Stage.S4_VALIDATE


def test_undefined_transition_is_rejected():
    with pytest.raises(ValueError, match="undefined stage transition"):
        StageMachine.default().transition(Stage.S0_INITIALIZE, "cad_completed")


def test_stage_configuration_covers_every_stage():
    config = json.loads(
        Path("config/orchestration/stage_machine.json").read_text(encoding="utf-8")
    )

    assert set(config["transitions"]) == {stage.value for stage in Stage}
