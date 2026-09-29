import json

import pytest

from gencore.cad_operations import IdempotencyLedger


def test_completed_operation_is_not_executed_twice(tmp_path):
    ledger = IdempotencyLedger(tmp_path, run_id="run-1")
    recorded = ledger.record(
        "idem:" + "a" * 64,
        {"status": "completed", "artifact_refs": []},
    )

    assert ledger.lookup("idem:" + "a" * 64) == recorded
    assert recorded["status"] == "completed"
    assert len(list((tmp_path / "runs/state/run-1/cad_operations").glob("*.json"))) == 1


def test_ledger_is_idempotent_and_rejects_conflicting_rewrite(tmp_path):
    ledger = IdempotencyLedger(tmp_path, run_id="run-1")
    key = "idem:" + "b" * 64
    first = ledger.record(key, {"status": "completed", "artifact_refs": []})
    second = ledger.record(key, {"status": "completed", "artifact_refs": []})

    assert second == first
    with pytest.raises(ValueError, match="conflicting"):
        ledger.record(key, {"status": "failed", "artifact_refs": []})


def test_corrupt_or_mismatched_ledger_entry_is_rejected(tmp_path):
    ledger = IdempotencyLedger(tmp_path, run_id="run-1")
    key = "idem:" + "c" * 64
    ledger.record(key, {"status": "completed"})
    path = next((tmp_path / "runs/state/run-1/cad_operations").glob("*.json"))
    value = json.loads(path.read_text(encoding="utf-8"))
    value["idempotency_key"] = "idem:" + "d" * 64
    path.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(ValueError, match="mismatch"):
        ledger.lookup(key)


@pytest.mark.parametrize("run_id", ("../escape", "bad/name", "C:\\escape"))
def test_ledger_rejects_unsafe_run_ids(tmp_path, run_id):
    with pytest.raises(ValueError, match="run_id"):
        IdempotencyLedger(tmp_path, run_id=run_id)
