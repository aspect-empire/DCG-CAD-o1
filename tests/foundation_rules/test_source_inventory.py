import json
from pathlib import Path

from gencore.resources import foundation_resource_root


ROOT = foundation_resource_root()
REQUIRED_CLAUSES = {
    "D01-T01",
    "D01-P113",
    "D01-P119",
    "D01-P129",
    "D01-P143",
    "D01-P207",
    "D01-P216",
    "D01-P230",
    "D01-P235",
    "D01-P349",
    "D01-P350",
    "D01-P351",
    "D01-P398",
    "D01-P403",
    "D02-T01",
    "D02-P23",
    "D02-P34",
    "D02-P35",
    "D02-P36",
    "D02-P37",
    "D02-P40",
    "D02-P41",
    "D02-P42",
    "D02-P307",
    "D02-P314-318",
    "D02-P319-325",
    "D02-P341",
}


def load(relative_path):
    return json.loads((ROOT / relative_path).read_text(encoding="utf-8"))


def test_every_clause_has_document_hash_locator_authority_and_semantics():
    manifest = load("sources/source_manifest.json")
    inventory = load("sources/clause_inventory.json")
    documents = {item["source_id"]: item for item in manifest["documents"]}

    assert {item["clause_id"] for item in inventory["clauses"]} == REQUIRED_CLAUSES
    for clause in inventory["clauses"]:
        assert clause["source_id"] in documents
        assert len(documents[clause["source_id"]]["sha256"]) == 64
        assert clause["locator"]
        assert clause["normalized_semantics"]
        assert clause["normative_strength"] in {"shall", "should", "may", "informative"}
        assert clause["classification"] in {"deterministic", "advisory", "verification_required"}


def test_document_02_is_updated_draft_with_explicit_priority():
    manifest = load("sources/source_manifest.json")
    documents = {item["source_id"]: item for item in manifest["documents"]}

    assert manifest["precedence_policy"] == "explicit_doc02_then_doc01_else_conflicted"
    assert documents["foundation-rule-doc-01"]["priority"] == 10
    assert documents["foundation-rule-doc-02"]["priority"] == 20
    assert documents["foundation-rule-doc-02"]["maturity"] == "updated_draft"
    assert documents["foundation-rule-doc-01"]["sha256"] == "571673c017df25a58cd0f075da7d87d0656dfa9d4a8bf0dc79b9ccb25fb8d8db"
    assert documents["foundation-rule-doc-02"]["sha256"] == "184c44ac8369df7728333376bc75bee911a2900a202f298a278ca97de017c08d"


def test_review_register_separates_advisory_and_conflicting_records():
    review = load("reviews/rule_review_v1.json")

    assert review["production_authority"] == "engineering_review_required"
    assert review["unresolved_conflicts"] == []
    assert "D02-P314-318" in review["advisory_clause_ids"]
    assert "D02-P40" in review["advisory_clause_ids"]
