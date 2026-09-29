"""Engineering artifact persistence port."""

from typing import Any, Mapping, Protocol


class ArtifactRepository(Protocol):
    def put_artifact(self, locator: str, content: bytes) -> Mapping[str, Any]: ...

    def verify_artifact(self, artifact_ref: Mapping[str, Any]) -> bool: ...


__all__ = ["ArtifactRepository"]
