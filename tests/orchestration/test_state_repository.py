import json

import pytest

from gencore.design_state import GraphOperation, GraphProposal
from gencore.orchestration import DesignExecutionPackage, Stage
from gencore.orchestration.state_repository import WorkspaceStateRepository


def proposal(base):
    operation = GraphOperation(
        "add_node",
        "node:a",
        {
            "uid": "node:a",
            "view": "product_function",
            "node_type": "EngineeringObject",
            "state": "observed",
        },
    )
    return GraphProposal.create(
        "run-1",
        base,
        (),
        (operation.target,),
        (operation,),
        (),
        ("schema", "write_set"),
    )


def package(version):
    return DesignExecutionPackage.create(
        task_id="GEN-001",
        scenario_id="SCN-01",
        run_id="run-1",
        graph_version=version,
        stage=Stage.S0_INITIALIZE,
        design_intent={"object": "框架式基座"},
    )


def test_repository_reopens_same_head_from_events(tmp_path):
    first = WorkspaceStateRepository(tmp_path, run_id="run-1")
    committed = first.commit(proposal(first.head.version_id))

    second = WorkspaceStateRepository(tmp_path, run_id="run-1")

    assert second.head.version_id == committed.version_id
    assert second.read_snapshot() == first.read_snapshot()
    assert second.changes_since(second.genesis_version) == {"node:a"}


def test_package_write_is_content_addressed_and_atomic(tmp_path):
    repository = WorkspaceStateRepository(tmp_path, run_id="run-1")
    execution_package = package(repository.head.version_id)

    path = repository.save_package(execution_package)

    assert path.name == execution_package.package_id.replace(":", "_") + ".json"
    assert repository.load_current_package("run-1") == execution_package
    assert json.loads(path.read_text(encoding="utf-8"))["package_id"] == execution_package.package_id


def test_repository_rejects_wrong_run_and_unsafe_run_ids(tmp_path):
    with pytest.raises(ValueError, match="one safe path segment"):
        WorkspaceStateRepository(tmp_path, run_id="../escape")
    repository = WorkspaceStateRepository(tmp_path, run_id="run-1")
    with pytest.raises(ValueError, match="does not match"):
        repository.save_package(
            DesignExecutionPackage.create(
                task_id="GEN-001",
                scenario_id="SCN-01",
                run_id="run-2",
                graph_version=repository.head.version_id,
                stage=Stage.S0_INITIALIZE,
                design_intent={},
            )
        )


def test_corrupt_event_log_is_not_silently_accepted(tmp_path):
    repository = WorkspaceStateRepository(tmp_path, run_id="run-1")
    repository.commit(proposal(repository.head.version_id))
    event_path = tmp_path / "runs" / "state" / "run-1" / "events.jsonl"
    event_path.write_text('{"kind":"broken"}\n', encoding="utf-8")

    with pytest.raises(ValueError, match="invalid version event"):
        WorkspaceStateRepository(tmp_path, run_id="run-1")
