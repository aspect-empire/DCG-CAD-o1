from dataclasses import FrozenInstanceError

import pytest

from gencore.events import EngineeringEvent, EventSource, canonical_json


def source():
    return EventSource("artifact:abc", "input.json", "$.x", "a" * 64)


def test_event_id_is_canonical_and_round_trips():
    left = EngineeringEvent.create("R1", 1, "parameter.observed", "2026-01-01T00:00:00Z", "text", source(), {"b": 2, "a": 1})
    right = EngineeringEvent.create("R1", 1, "parameter.observed", "2026-01-01T00:00:00Z", "text", source(), {"a": 1, "b": 2})
    assert left.event_id == right.event_id
    assert EngineeringEvent.from_dict(left.to_dict()) == left
    assert canonical_json({"b": 2, "a": 1}) == '{"a":1,"b":2}'


def test_event_is_immutable_and_validated():
    event = EngineeringEvent.create("R1", 1, "x", "2026-01-01T00:00:00Z", "p", source(), {"x": [1]})
    with pytest.raises(FrozenInstanceError):
        event.run_id = "R2"
    with pytest.raises(TypeError):
        event.payload["x"] = 2
    with pytest.raises(ValueError):
        EngineeringEvent.create("", 0, "", "bad", "", source(), {})
