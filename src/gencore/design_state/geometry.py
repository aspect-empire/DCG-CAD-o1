"""Task-relevant geometry levels and resilient CATIA reference resolution."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Sequence


class GeometryLevel(str, Enum):
    ARTIFACT = "G0"
    ASSEMBLY_INSTANCE = "G1"
    FEATURE = "G2"
    BOUNDARY = "G3"
    KEYPOINT = "G4"
    DERIVED_SPATIAL = "G5"


@dataclass(frozen=True)
class GeometryReference:
    level: GeometryLevel
    semantic_role: str
    persistent_uri: str
    signature: tuple[float, ...]
    topology_neighbourhood: tuple[str, ...]
    tolerance: float

    def __post_init__(self) -> None:
        if not self.semantic_role or not self.persistent_uri or not self.signature:
            raise ValueError("geometry role, persistent URI and signature are required")
        if self.tolerance < 0:
            raise ValueError("geometry reference tolerance must be nonnegative")


@dataclass(frozen=True)
class Resolution:
    status: str
    resolved_uri: str | None
    candidate_uris: tuple[str, ...]


class ReferenceResolver:
    @staticmethod
    def _matches(reference: GeometryReference, candidate: Mapping[str, Any]) -> bool:
        signature = tuple(float(value) for value in candidate.get("signature", ()))
        if len(signature) != len(reference.signature):
            return False
        delta = max(abs(expected - actual) for expected, actual in zip(reference.signature, signature))
        return (
            candidate.get("role") == reference.semantic_role
            and delta <= reference.tolerance
            and tuple(candidate.get("neighbours", ())) == reference.topology_neighbourhood
        )

    def resolve(
        self,
        reference: GeometryReference,
        candidates: Sequence[Mapping[str, Any]],
    ) -> Resolution:
        ordered = sorted(candidates, key=lambda item: str(item.get("uri", "")))
        exact = [item for item in ordered if item.get("uri") == reference.persistent_uri]
        matches = [item for item in ordered if self._matches(reference, item)]
        match_uris = tuple(str(item["uri"]) for item in matches)
        if exact and exact[0] not in matches and matches:
            uris = tuple(sorted({reference.persistent_uri, *match_uris}))
            return Resolution("conflicted", None, uris)
        if len(matches) == 1:
            uri = match_uris[0]
            return Resolution("stable" if uri == reference.persistent_uri else "relocated", uri, (uri,))
        if len(matches) > 1:
            return Resolution("ambiguous", None, match_uris)
        return Resolution("lost", None, ())
