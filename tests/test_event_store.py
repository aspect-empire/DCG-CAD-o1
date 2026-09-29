from dataclasses import replace

import pytest

from gencore.event_store import EventConflictError, JsonlEventStore
from gencore.events import EngineeringEvent, EventSource


def event(value=8):
    return EngineeringEvent.create("R", 1, "parameter.observed", "2026-01-01T00:00:00Z", "test", EventSource("a", "x", "$.x", "b" * 64), {"value": value})


def test_append_replay_and_jsonl_round_trip(tmp_path):
    store = JsonlEventStore(tmp_path / "events.jsonl")
    assert store.append(event()) is True
    assert store.append(event()) is False
    assert store.replay([event(), event(9)]) == 1
    assert [e.payload["value"] for e in store.read()] == [8, 9]


def test_same_id_with_different_semantics_is_rejected(tmp_path):
    store = JsonlEventStore(tmp_path / "events.jsonl")
    original = event()
    store.append(original)
    forged = replace(original, payload={"value": 9})
    with pytest.raises(EventConflictError):
        store.append(forged)
