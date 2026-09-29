"""Compiled rule packages to parameter/rule and evidence graph records."""

from __future__ import annotations

import json
from pathlib import Path

from gencore.foundation_rules.compiler import CompiledRulePackage
from gencore.resources import foundation_resource_root

from ..ontology import View
from ..proposals import GraphOperation, GraphProposal
from ..records import DesignNode, EvidenceRef
from .common import proposal_from_operations


class RulePackageAdapter:
    def __init__(self, source_manifest: dict | None = None):
        if source_manifest is None:
            path = foundation_resource_root() / "sources" / "source_manifest.json"
            source_manifest = json.loads(path.read_text(encoding="utf-8"))
        self.documents = {item["source_id"]: item for item in source_manifest["documents"]}

    def adapt(self, package: CompiledRulePackage, *, run_id: str, base_version: str) -> GraphProposal:
        operations: list[GraphOperation] = []
        for rule in package.rules:
            document = self.documents[rule["source_id"]]
            evidence = EvidenceRef(
                f"artifact:{rule['source_id']}",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                str(rule["source_locator"]),
                str(document["sha256"]),
            )
            node = DesignNode.create(
                View.PARAMETER_RULE,
                "RuleClause",
                str(rule["rule_id"]),
                dict(rule),
                (evidence,),
            )
            operations.append(GraphOperation("add_node", node.uid, node.to_dict()))
        return proposal_from_operations(
            run_id=run_id,
            base_version=base_version,
            operations=operations,
            premise_event_ids=(),
        )
