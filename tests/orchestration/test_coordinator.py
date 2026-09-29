def test_coordinator_dispatches_one_ready_task_per_step(scripted_ports):
    result = scripted_ports.coordinator.step("run-1")

    assert result.dispatched_task_id == "task:scene"
    assert scripted_ports.agent_runtime.calls == [
        ("task:scene", scripted_ports.genesis)
    ]
    current = scripted_ports.repository.load_current_package()
    assert current.provenance[-1]["task_id"] == "task:scene"
    assert current.provenance[-1]["status"] == "completed"


def test_second_step_does_not_repeat_completed_task(scripted_ports):
    first = scripted_ports.coordinator.step("run-1")
    second = scripted_ports.coordinator.step("run-1")

    assert first.dispatched_task_id == "task:scene"
    assert second.dispatched_task_id == "task:validate"
    assert [item[0] for item in scripted_ports.agent_runtime.calls] == [
        "task:scene",
        "task:validate",
    ]
