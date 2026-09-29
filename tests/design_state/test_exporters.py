import json

from gencore.design_state import DesignStateStore, GraphOperation, GraphProposal
from gencore.exporters import export_design_version


def committed_store():
    store = DesignStateStore()
    operation = GraphOperation(
        "add_node",
        "node:panel-thickness",
        {
            "uid": "node:panel-thickness",
            "view": "parameter_rule",
            "node_type": "ParameterValue",
            "state": "derived",
            "evidence": [{"locator": "table:unit_area_load_thickness"}],
            "attributes": {"name": "板厚", "value": "10", "unit": "mm"},
        },
    )
    proposal = GraphProposal.create("export-1", store.head.version_id, (), (operation.target,), (operation,), (), ("schema", "write_set"))
    store.commit(proposal)
    return store


def test_json_export_keeps_version_view_state_and_evidence(tmp_path):
    store = committed_store()

    path = export_design_version(store, store.head.version_id, tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["version_id"] == store.head.version_id
    assert payload["graph_hash"] == store.head.graph_hash
    assert all("view" in node and "state" in node and "evidence" in node for node in payload["nodes"])


def test_export_is_byte_stable(tmp_path):
    store = committed_store()
    first = export_design_version(store, store.head.version_id, tmp_path).read_bytes()
    second = export_design_version(store, store.head.version_id, tmp_path).read_bytes()

    assert first == second
