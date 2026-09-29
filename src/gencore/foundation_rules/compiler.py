"""Validation and compilation of curated foundation rule packages."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from gencore.design_state.records import _freeze, _thaw
from gencore.events import canonical_hash
from gencore.resources import foundation_resource_root


SUPPORTED_OPERATORS = frozenset({
    "conditional",
    "decision_table",
    "formula",
    "increase_grade",
    "minimum",
    "minimum_ratio",
    "non_stacking",
    "permission",
    "range",
    "range_ratio",
    "ratio_limit",
    "select_max",
})


class RuleCompilationError(ValueError):
    """Raised when a curated package cannot be compiled without ambiguity."""


@dataclass(frozen=True)
class CompiledRulePackage:
    package_id: str
    schema_version: str
    rules: tuple[Mapping[str, Any], ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "rules", tuple(_freeze(rule) for rule in self.rules))

    def to_dict(self) -> dict[str, Any]:
        return {
            "package_id": self.package_id,
            "schema_version": self.schema_version,
            "rules": [_thaw(rule) for rule in self.rules],
        }

    @property
    def content_hash(self) -> str:
        return self.recompute_hash()

    def recompute_hash(self) -> str:
        return canonical_hash(self.to_dict())

    def rule(self, rule_id: str) -> Mapping[str, Any]:
        for rule in self.rules:
            if rule["rule_id"] == rule_id:
                return rule
        raise KeyError(rule_id)


def compile_rule_package(
    raw_package: Mapping[str, Any],
    source_manifest: Mapping[str, Any],
    clause_inventory: Mapping[str, Any],
) -> CompiledRulePackage:
    documents = {item["source_id"]: item for item in source_manifest["documents"]}
    clauses = {item["clause_id"]: item for item in clause_inventory["clauses"]}
    rules = list(raw_package.get("rules", ()))
    rule_ids = [str(rule.get("rule_id", "")) for rule in rules]
    duplicates = sorted({rule_id for rule_id in rule_ids if rule_ids.count(rule_id) > 1})
    if duplicates:
        raise RuleCompilationError("duplicate rule_id: " + ", ".join(duplicates))

    by_scope: dict[str, list[Mapping[str, Any]]] = {}
    validated_rules: list[dict[str, Any]] = []
    for rule in rules:
        clause_id = rule.get("source_clause_id")
        if clause_id not in clauses:
            raise RuleCompilationError(f"unknown source clause: {clause_id}")
        clause = clauses[clause_id]
        document = documents[clause["source_id"]]
        if clause["classification"] != "deterministic":
            raise RuleCompilationError(f"non-deterministic source clause is not executable: {clause_id}")
        if int(rule.get("priority", -1)) != int(document["priority"]):
            raise RuleCompilationError(f"rule priority does not match source authority: {rule['rule_id']}")
        expression = rule.get("expression") or {}
        if expression.get("op") not in SUPPORTED_OPERATORS:
            raise RuleCompilationError(f"unsupported operator: {expression.get('op')}")
        scope = str(rule.get("scope", ""))
        if not scope:
            raise RuleCompilationError(f"rule scope is required: {rule['rule_id']}")
        by_scope.setdefault(scope, []).append(rule)
        enriched = _thaw(_freeze(rule))
        enriched["source_id"] = clause["source_id"]
        enriched["source_locator"] = clause["locator"]
        enriched["normative_strength"] = clause["normative_strength"]
        validated_rules.append(enriched)

    for scope, scoped_rules in by_scope.items():
        priorities = {int(rule["priority"]) for rule in scoped_rules}
        if len(scoped_rules) > 1 and len(priorities) > 1:
            lower = [rule for rule in scoped_rules if int(rule["priority"]) < max(priorities)]
            if any(not rule.get("fallback_only", False) for rule in lower):
                raise RuleCompilationError(f"lower-priority override in scope {scope}")

    ordered = tuple(sorted(validated_rules, key=lambda item: item["rule_id"]))
    return CompiledRulePackage(str(raw_package["package_id"]), str(raw_package["schema_version"]), ordered)


def _rule_root() -> Path:
    return foundation_resource_root()


def load_default_package() -> CompiledRulePackage:
    root = _rule_root()
    raw = json.loads((root / "packages" / "foundation_rules_v1.json").read_text(encoding="utf-8"))
    manifest = json.loads((root / "sources" / "source_manifest.json").read_text(encoding="utf-8"))
    inventory = json.loads((root / "sources" / "clause_inventory.json").read_text(encoding="utf-8"))
    return compile_rule_package(raw, manifest, inventory)
