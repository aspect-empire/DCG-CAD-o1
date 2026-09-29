"""Immutable, content-addressed engineering event envelopes."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import json
from types import MappingProxyType
from typing import Any, Mapping


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(k): _freeze(v) for k, v in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, set):
        return tuple(sorted((_freeze(item) for item in value), key=repr))
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


def canonical_json(value: Any) -> str:
    """Return clone- and ordering-stable UTF-8 JSON text."""
    return json.dumps(_thaw(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class EventSource:
    artifact_id: str
    path: str
    locator: str
    sha256: str

    def __post_init__(self) -> None:
        if not all(isinstance(item, str) and item for item in (self.artifact_id, self.path, self.locator, self.sha256)):
            raise ValueError("event source fields must be non-empty strings")
        if len(self.sha256) != 64 or any(c not in "0123456789abcdefABCDEF" for c in self.sha256):
            raise ValueError("source sha256 must be a 64-character hexadecimal digest")

    def to_dict(self) -> dict[str, str]:
        return {"artifact_id": self.artifact_id, "path": self.path, "locator": self.locator, "sha256": self.sha256.lower()}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "EventSource":
        return cls(**{key: value[key] for key in ("artifact_id", "path", "locator", "sha256")})


@dataclass(frozen=True)
class EngineeringEvent:
    schema_version: str
    event_id: str
    run_id: str
    sequence_no: int
    event_type: str
    occurred_at: str
    producer: str
    source: EventSource
    payload: Mapping[str, Any] = field(default_factory=dict)
    premise_event_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "payload", _freeze(self.payload))
        object.__setattr__(self, "premise_event_ids", tuple(self.premise_event_ids))
        if self.schema_version != "1.0":
            raise ValueError("unsupported schema_version")
        if not self.event_id.startswith("evt:") or len(self.event_id) != 68:
            raise ValueError("event_id must be evt:<sha256>")
        if not self.run_id or self.sequence_no < 1 or not self.event_type or not self.producer:
            raise ValueError("run_id, positive sequence_no, event_type and producer are required")
        try:
            datetime.fromisoformat(self.occurred_at.replace("Z", "+00:00"))
        except (TypeError, ValueError) as exc:
            raise ValueError("occurred_at must be ISO-8601") from exc

    @staticmethod
    def _semantic_dict(*, schema_version: str, run_id: str, sequence_no: int, event_type: str,
                       occurred_at: str, producer: str, source: EventSource,
                       payload: Mapping[str, Any], premise_event_ids: tuple[str, ...]) -> dict[str, Any]:
        return {
            "schema_version": schema_version, "run_id": run_id, "sequence_no": sequence_no,
            "event_type": event_type, "occurred_at": occurred_at, "producer": producer,
            "source": source.to_dict(), "payload": _thaw(payload),
            "premise_event_ids": list(premise_event_ids),
        }

    @classmethod
    def create(cls, run_id: str, sequence_no: int, event_type: str, occurred_at: str,
               producer: str, source: EventSource, payload: Mapping[str, Any],
               premise_event_ids: tuple[str, ...] | list[str] = ()) -> "EngineeringEvent":
        premises = tuple(premise_event_ids)
        semantic = cls._semantic_dict(schema_version="1.0", run_id=run_id, sequence_no=sequence_no,
                                      event_type=event_type, occurred_at=occurred_at, producer=producer,
                                      source=source, payload=payload, premise_event_ids=premises)
        return cls("1.0", f"evt:{canonical_hash(semantic)}", run_id, sequence_no, event_type,
                   occurred_at, producer, source, payload, premises)

    def semantic_dict(self) -> dict[str, Any]:
        return self._semantic_dict(schema_version=self.schema_version, run_id=self.run_id,
                                   sequence_no=self.sequence_no, event_type=self.event_type,
                                   occurred_at=self.occurred_at, producer=self.producer,
                                   source=self.source, payload=self.payload,
                                   premise_event_ids=self.premise_event_ids)

    def to_dict(self) -> dict[str, Any]:
        return {"event_id": self.event_id, **self.semantic_dict()}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any], *, verify_id: bool = True) -> "EngineeringEvent":
        event = cls(value["schema_version"], value["event_id"], value["run_id"], int(value["sequence_no"]),
                    value["event_type"], value["occurred_at"], value["producer"],
                    EventSource.from_dict(value["source"]), value.get("payload", {}),
                    tuple(value.get("premise_event_ids", ())))
        expected = f"evt:{canonical_hash(event.semantic_dict())}"
        if verify_id and event.event_id != expected:
            raise ValueError("event_id does not match canonical semantic content")
        return event
