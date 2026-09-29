"""Immutable, content-addressed records shared by all design-state views."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from gencore.events import canonical_hash

from .ontology import ValueState, View


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
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


@dataclass(frozen=True)
class EvidenceRef:
    artifact_id: str
    media_type: str
    locator: str
    sha256: str

    def __post_init__(self) -> None:
        if not all(isinstance(value, str) and value for value in (self.artifact_id, self.media_type, self.locator)):
            raise ValueError("artifact_id, media_type and locator must be non-empty strings")
        if len(self.sha256) != 64 or any(character not in "0123456789abcdefABCDEF" for character in self.sha256):
            raise ValueError("sha256 must be a 64-character hexadecimal digest")
        object.__setattr__(self, "sha256", self.sha256.lower())

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class DesignNode:
    uid: str
    view: View
    node_type: str
    natural_key: str
    attributes: Mapping[str, Any]
    evidence: tuple[EvidenceRef, ...] = field(default_factory=tuple)
    state: ValueState = ValueState.OBSERVED

    def __post_init__(self) -> None:
        object.__setattr__(self, "attributes", _freeze(self.attributes))
        object.__setattr__(self, "evidence", tuple(self.evidence))

    @classmethod
    def create(
        cls,
        view: View,
        node_type: str,
        natural_key: str,
        attributes: Mapping[str, Any],
        evidence: Sequence[EvidenceRef],
        state: ValueState = ValueState.OBSERVED,
    ) -> "DesignNode":
        if not node_type or not natural_key:
            raise ValueError("node_type and natural_key must be non-empty strings")
        if state is ValueState.UNKNOWN and not attributes.get("missing_inputs"):
            raise ValueError("unknown values require missing_inputs")
        identity = {"view": view.value, "node_type": node_type, "natural_key": natural_key}
        return cls(
            "node:" + canonical_hash(identity),
            view,
            node_type,
            natural_key,
            attributes,
            tuple(evidence),
            state,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "uid": self.uid,
            "view": self.view.value,
            "node_type": self.node_type,
            "natural_key": self.natural_key,
            "attributes": _thaw(self.attributes),
            "evidence": [item.to_dict() for item in self.evidence],
            "state": self.state.value,
        }
