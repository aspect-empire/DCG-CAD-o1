"""Runtime event publication port."""

from typing import Any, Mapping, Protocol


class EventPublisher(Protocol):
    def publish(self, event: Mapping[str, Any]) -> Mapping[str, Any]: ...


__all__ = ["EventPublisher"]
