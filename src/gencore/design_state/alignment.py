"""Deterministic multimodal entity alignment with explicit ambiguity."""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Any, Mapping, Sequence


WEIGHTS = {
    "name": 0.30,
    "hierarchy": 0.15,
    "geometry": 0.20,
    "interface": 0.20,
    "context": 0.10,
    "conflict": 0.05,
}


def _normalized_name(value: Any) -> str:
    text = str(value or "").strip().lower()
    for token in (" ", "_", "-", "式"):
        text = text.replace(token, "")
    return text


@dataclass(frozen=True)
class AlignmentResult:
    status: str
    target_uid: str | None
    candidate_uids: tuple[str, ...]
    score: float
    score_components: Mapping[str, float]
    ranked_scores: tuple[tuple[str, float], ...]


class AlignmentEngine:
    def __init__(self, accept_threshold: float = 0.75, ambiguity_margin: float = 0.1):
        self.accept_threshold = accept_threshold
        self.ambiguity_margin = ambiguity_margin

    @staticmethod
    def _geometry_similarity(source: Any, candidate: Any) -> float:
        if not isinstance(source, Sequence) or isinstance(source, (str, bytes)):
            return 0.0
        if not isinstance(candidate, Sequence) or isinstance(candidate, (str, bytes)) or len(source) != len(candidate):
            return 0.0
        distance = sqrt(sum((float(left) - float(right)) ** 2 for left, right in zip(source, candidate)))
        return 1.0 / (1.0 + distance)

    @staticmethod
    def _context_similarity(source: Any, candidate: Any) -> float:
        left, right = set(source or ()), set(candidate or ())
        return len(left & right) / len(left | right) if left or right else 0.0

    def _score(self, source: Mapping[str, Any], candidate: Mapping[str, Any]) -> dict[str, float]:
        components = {key: 0.0 for key in WEIGHTS}
        active = {"name", "conflict"}
        components["name"] = float(_normalized_name(source.get("name")) == _normalized_name(candidate.get("name")))
        components["conflict"] = 0.0 if candidate.get("conflict", False) else 1.0
        if source.get("parent") is not None and candidate.get("parent") is not None:
            active.add("hierarchy")
            components["hierarchy"] = float(source["parent"] == candidate["parent"])
        if source.get("geometry_signature") is not None and candidate.get("geometry_signature") is not None:
            active.add("geometry")
            components["geometry"] = self._geometry_similarity(source["geometry_signature"], candidate["geometry_signature"])
        if source.get("interface") is not None and candidate.get("interface") is not None:
            active.add("interface")
            components["interface"] = float(source["interface"] == candidate["interface"])
        if source.get("context") is not None and candidate.get("context") is not None:
            active.add("context")
            components["context"] = self._context_similarity(source["context"], candidate["context"])
        denominator = sum(WEIGHTS[name] for name in active)
        components["total"] = sum(WEIGHTS[name] * components[name] for name in active) / denominator
        return components

    def align(self, source: Mapping[str, Any], candidates: Sequence[Mapping[str, Any]]) -> AlignmentResult:
        scored = [(self._score(source, candidate), str(candidate["uid"])) for candidate in candidates]
        scored.sort(key=lambda item: (-item[0]["total"], item[1]))
        if not scored:
            return AlignmentResult("unresolved", None, (), 0.0, {key: 0.0 for key in WEIGHTS}, ())
        ranked = tuple((uid, scores["total"]) for scores, uid in scored)
        top_components, top_uid = scored[0]
        visible_components = {key: top_components[key] for key in WEIGHTS}
        top_score = top_components["total"]
        if top_score < self.accept_threshold:
            return AlignmentResult("unresolved", None, tuple(uid for _, uid in scored), top_score, visible_components, ranked)
        close = tuple(uid for scores, uid in scored if top_score - scores["total"] <= self.ambiguity_margin)
        if len(close) > 1:
            return AlignmentResult("ambiguous", None, close, top_score, visible_components, ranked)
        return AlignmentResult("aligned", top_uid, (top_uid,), top_score, visible_components, ranked)
