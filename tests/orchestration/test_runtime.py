from gencore.orchestration import AgentOutcome, DesignDecision
from gencore.orchestration.runtime import DesignRuntime


def test_runtime_never_uses_agent_requested_acceptance(scripted_ports):
    scripted_ports.agent_runtime.outcomes["task:validate"] = AgentOutcome(
        status="completed",
        requested_decision=DesignDecision.RUNNING,
    )

    result = DesignRuntime(scripted_ports.coordinator).run("run-1", max_steps=20)

    assert result.decision is not DesignDecision.ACCEPTED
    assert result.steps <= 20
    assert result.dispatched_task_ids == ("task:scene", "task:validate")


def test_runtime_stops_at_max_steps_without_claiming_acceptance(scripted_ports):
    result = DesignRuntime(scripted_ports.coordinator).run("run-1", max_steps=1)

    assert result.decision is DesignDecision.ABSTAINED
    assert result.stop_reason == "max_steps"


def test_runtime_stops_when_validation_requests_human_review(scripted_ports):
    scripted_ports.agent_runtime.outcomes["task:validate"] = AgentOutcome(
        status="blocked",
        missing_inputs=("independent evidence is missing",),
        requested_decision=DesignDecision.HUMAN_REQUIRED,
    )

    result = DesignRuntime(scripted_ports.coordinator).run("run-1", max_steps=20)

    assert result.decision is DesignDecision.HUMAN_REQUIRED
    assert result.stop_reason == "terminal_decision"
    assert result.dispatched_task_ids == ("task:scene", "task:validate")
    assert (
        scripted_ports.repository.load_current_package().current_decision
        is DesignDecision.HUMAN_REQUIRED
    )
