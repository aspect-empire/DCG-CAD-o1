from pathlib import Path

import pytest

from gencore.infrastructure.orchestration_storage import WorkspaceOrchestrationStorage


def test_checkpoint_and_approval_are_bound_to_graph_version(tmp_path):
    storage = WorkspaceOrchestrationStorage(tmp_path, run_id="run-1")
    storage.save_checkpoint(
        {
            "checkpoint_id": "cp:1",
            "graph_version": "ver:1",
            "stage": "S2_PLAN_GEOMETRY",
        }
    )

    approval = storage.record_approval(
        {
            "operation_id": "op:1",
            "graph_version": "ver:1",
            "decision": "approve_once",
            "operator": "tester",
        }
    )

    assert storage.load_checkpoint()["graph_version"] == "ver:1"
    assert approval["event_id"].startswith("evt:")
    assert storage.read_events() == [approval]


def test_artifact_repository_verifies_hash_and_relative_path(tmp_path):
    storage = WorkspaceOrchestrationStorage(tmp_path, run_id="run-1")

    ref = storage.put_artifact("cad/model.stl", b"solid model\nendsolid model\n")

    assert ref["locator"] == "runs/state/run-1/artifacts/cad/model.stl"
    assert storage.verify_artifact(ref) is True
    (tmp_path / Path(ref["locator"])).write_bytes(b"tampered")
    assert storage.verify_artifact(ref) is False


def test_workspace_services_reject_path_escape_and_unversioned_checkpoint(tmp_path):
    storage = WorkspaceOrchestrationStorage(tmp_path, run_id="run-1")
    with pytest.raises(ValueError, match="graph_version"):
        storage.save_checkpoint({"checkpoint_id": "cp:1"})
    with pytest.raises(ValueError, match="relative"):
        storage.put_artifact("../outside.stl", b"data")


def test_runtime_events_preserve_append_sequence_and_deduplicate(tmp_path):
    storage = WorkspaceOrchestrationStorage(tmp_path, run_id="run-1")

    first = storage.publish({"event_type": "task.started", "payload": {"task": "a"}})
    second = storage.publish({"event_type": "task.completed", "payload": {"task": "a"}})
    duplicate = storage.publish({"event_type": "task.started", "payload": {"task": "a"}})

    assert [item["sequence_no"] for item in storage.read_events()] == [1, 2]
    assert duplicate == first
    assert second["sequence_no"] == 2
