"""Append-only JSONL persistence for engineering events."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterable

from contextlib import contextmanager

from .events import EngineeringEvent, canonical_json


class EventConflictError(ValueError):
    pass


@contextmanager
def _exclusive_file_lock(path: Path):
    """Cross-process advisory lock stored beside one JSONL event log."""
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as handle:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
            unlock = lambda: msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            unlock = lambda: fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        try:
            yield
        finally:
            unlock()


class JsonlEventStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def read(self) -> list[EngineeringEvent]:
        if not self.path.exists():
            return []
        events: list[EngineeringEvent] = []
        seen: dict[str, str] = {}
        with self.path.open("r", encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                try:
                    event = EngineeringEvent.from_dict(json.loads(line))
                except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                    raise ValueError(f"invalid event at JSONL line {line_no}") from exc
                semantic = canonical_json(event.semantic_dict())
                if event.event_id in seen and seen[event.event_id] != semantic:
                    raise EventConflictError(f"conflicting event_id {event.event_id}")
                if event.event_id not in seen:
                    events.append(event)
                    seen[event.event_id] = semantic
        return events

    def append(self, event: EngineeringEvent) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with _exclusive_file_lock(self.path):
            existing = {item.event_id: canonical_json(item.semantic_dict()) for item in self.read()}
            semantic = canonical_json(event.semantic_dict())
            if event.event_id in existing:
                if existing[event.event_id] != semantic:
                    raise EventConflictError(f"conflicting event_id {event.event_id}")
                return False
            with self.path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(canonical_json(event.to_dict()) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            return True

    def replay(self, events: Iterable[EngineeringEvent]) -> int:
        return sum(1 for event in events if self.append(event))


EventStore = JsonlEventStore
