from gencore.design_state.adapters.rules import RulePackageAdapter
from gencore.foundation_rules import load_default_package


def test_rule_package_adapter_links_rules_to_source_evidence():
    package = load_default_package()

    proposal = RulePackageAdapter().adapt(package, run_id="rules-1", base_version="ver:base")
    rule_nodes = [
        operation.value
        for operation in proposal.operations
        if operation.kind == "add_node" and operation.value["node_type"] == "RuleClause"
    ]

    thickness = next(node for node in rule_nodes if node["attributes"]["rule_id"] == "thickness.unit_area.v1")
    assert thickness["view"] == "parameter_rule"
    assert thickness["evidence"][0]["locator"] == "table:unit_area_load_thickness"
    assert proposal.premise_event_ids == ()
