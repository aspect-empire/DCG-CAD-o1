"""Typed foundation-template matching without model or network dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from types import MappingProxyType
from typing import Any, Mapping

from gencore.events import canonical_hash


_NUMERIC_KINDS = {"numeric"}
_SET_KINDS = {"set"}
_ENUM_KINDS = {"enum"}


def _decimal(value: Any, field: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a decimal number") from exc
    if not result.is_finite():
        raise ValueError(f"{field} must be a finite decimal number")
    return result


def _decimal_text(value: Decimal) -> str:
    normalized = value.normalize()
    return format(normalized, "f")


@dataclass(frozen=True)
class CandidateScore:
    template_id: str
    total_score: Decimal
    evidence_coverage: Decimal
    dimension_scores: Mapping[str, Decimal]
    satisfied: tuple[str, ...]
    missing: tuple[str, ...]
    conflicts: tuple[str, ...]
    reusable_parameters: tuple[str, ...]
    recompute_parameters: tuple[str, ...]
    artifact_refs: tuple[Mapping[str, Any], ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "dimension_scores", MappingProxyType(dict(self.dimension_scores))
        )
        object.__setattr__(
            self,
            "artifact_refs",
            tuple(MappingProxyType(dict(item)) for item in self.artifact_refs),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "template_id": self.template_id,
            "total_score": _decimal_text(self.total_score),
            "score": _decimal_text(self.total_score),
            "evidence_coverage": _decimal_text(self.evidence_coverage),
            "dimension_scores": {
                key: _decimal_text(value)
                for key, value in sorted(self.dimension_scores.items())
            },
            "satisfied": list(self.satisfied),
            "missing": list(self.missing),
            "conflicts": list(self.conflicts),
            "reusable_parameters": list(self.reusable_parameters),
            "recompute_parameters": list(self.recompute_parameters),
            "artifact_refs": [dict(item) for item in self.artifact_refs],
        }


@dataclass(frozen=True)
class MatchResult:
    status: str
    candidates: tuple[CandidateScore, ...]
    filtered: tuple[Mapping[str, str], ...]
    content_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "filtered",
            tuple(MappingProxyType(dict(item)) for item in self.filtered),
        )

    def semantic_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "candidates": [item.to_dict() for item in self.candidates],
            "filtered": [dict(item) for item in self.filtered],
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self.semantic_dict(), "content_hash": self.content_hash}


class FoundationCaseMatcher:
    """Rank compatible templates using frozen, auditable matching dimensions."""

    def __init__(
        self, template_registry: Mapping[str, Any], weights: Mapping[str, Any]
    ) -> None:
        self._templates = tuple(template_registry.get("templates", ()))
        self._dimensions = tuple(weights.get("dimensions", ()))
        if not self._templates:
            raise ValueError("template registry must contain templates")
        if not self._dimensions:
            raise ValueError("matching weights must contain dimensions")

    def match(
        self, query: Mapping[str, Any], *, top_k: int | None = None
    ) -> MatchResult:
        if top_k is not None and top_k < 1:
            raise ValueError("top_k must be positive")
        self._validate_query(query)
        filtered: list[dict[str, str]] = []
        candidates: list[CandidateScore] = []
        for template in self._templates:
            hard_conflicts = self._hard_conflicts(query, template)
            if hard_conflicts:
                filtered.extend(hard_conflicts)
                continue
            candidates.append(self._score(query, template))

        candidates.sort(key=lambda item: (-item.total_score, item.template_id))
        selected = tuple(candidates[:top_k] if top_k is not None else candidates)
        status = "candidate" if selected else "unknown"
        semantic = {
            "status": status,
            "candidates": [item.to_dict() for item in selected],
            "filtered": filtered,
        }
        return MatchResult(
            status=status,
            candidates=selected,
            filtered=tuple(filtered),
            content_hash=canonical_hash(semantic),
        )

    def _validate_query(self, query: Mapping[str, Any]) -> None:
        for dimension in self._dimensions:
            field = str(dimension["field"])
            value = query.get(field)
            if value is not None and dimension["kind"] in _NUMERIC_KINDS:
                _decimal(value, field)

    @staticmethod
    def _hard_conflicts(
        query: Mapping[str, Any], template: Mapping[str, Any]
    ) -> list[dict[str, str]]:
        conflicts: list[dict[str, str]] = []
        template_id = str(template["template_id"])
        for field in sorted(template.get("hard_fields", {})):
            actual = query.get(field)
            allowed = tuple(template["hard_fields"][field])
            if actual is not None and actual not in allowed:
                conflicts.append(
                    {
                        "template_id": template_id,
                        "field": field,
                        "reason": "hard_conflict",
                        "query_value": str(actual),
                        "allowed_values": ",".join(map(str, allowed)),
                    }
                )
        return conflicts

    def _score(
        self, query: Mapping[str, Any], template: Mapping[str, Any]
    ) -> CandidateScore:
        scores: dict[str, Decimal] = {}
        satisfied: list[str] = []
        missing: list[str] = []
        used_weight = Decimal("0")
        total_weight = sum(
            (_decimal(item["weight"], str(item["field"])) for item in self._dimensions),
            Decimal("0"),
        )
        weighted_score = Decimal("0")
        template_values = template.get("match_values", {})

        for dimension in self._dimensions:
            field = str(dimension["field"])
            value = query.get(field)
            reference = template_values.get(field)
            if value is None or reference is None:
                missing.append(field)
                continue
            weight = _decimal(dimension["weight"], field)
            score = self._dimension_score(dimension, value, reference)
            scores[field] = score
            used_weight += weight
            weighted_score += score * weight
            if score == Decimal("1"):
                satisfied.append(field)

        total_score = (
            weighted_score / used_weight if used_weight else Decimal("0")
        ).quantize(Decimal("0.000001"))
        coverage = (
            used_weight / total_weight if total_weight else Decimal("0")
        ).quantize(Decimal("0.000001"))
        return CandidateScore(
            template_id=str(template["template_id"]),
            total_score=total_score,
            evidence_coverage=coverage,
            dimension_scores=scores,
            satisfied=tuple(satisfied),
            missing=tuple(missing),
            conflicts=(),
            reusable_parameters=tuple(template.get("reusable_parameters", ())),
            recompute_parameters=tuple(template.get("recompute_parameters", ())),
            artifact_refs=tuple(template.get("artifact_refs", ())),
        )

    @staticmethod
    def _dimension_score(
        dimension: Mapping[str, Any], value: Any, reference: Any
    ) -> Decimal:
        kind = str(dimension["kind"])
        field = str(dimension["field"])
        if kind in _NUMERIC_KINDS:
            low = _decimal(dimension["min"], field)
            high = _decimal(dimension["max"], field)
            span = high - low
            if span <= 0:
                raise ValueError(f"{field} numeric range must be positive")
            distance = abs(_decimal(value, field) - _decimal(reference, field))
            return max(Decimal("0"), Decimal("1") - distance / span)
        if kind in _ENUM_KINDS:
            return Decimal("1") if str(value) == str(reference) else Decimal("0")
        if kind in _SET_KINDS:
            observed = {str(item) for item in value}
            expected = {str(item) for item in reference}
            union = observed | expected
            return (
                Decimal(len(observed & expected)) / Decimal(len(union))
                if union
                else Decimal("1")
            )
        raise ValueError(f"unsupported matching kind: {kind}")
