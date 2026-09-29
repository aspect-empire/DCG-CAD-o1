"""Framework checkpoint persistence port."""

from typing import Any, Mapping, Protocol


class CheckpointStore(Protocol):
    def load_checkpoint(self) -> Mapping[str, Any] | None: ...

    def save_checkpoint(self, checkpoint: Mapping[str, Any]) -> None: ...


__all__ = ["CheckpointStore"]
