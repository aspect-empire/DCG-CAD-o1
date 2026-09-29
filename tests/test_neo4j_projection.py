import sys

from gencore.adapters import TextAdapter
from gencore.design_state import DesignStateStore, GraphOperation, GraphProposal
from gencore.graph import EngineeringGraph
from gencore.neo4j_projection import build_cypher_batches, build_design_state_cypher_batches, write_cypher_batches


def _graph():
    event = TextAdapter().adapt(
        run_id="neo4j-example", entity="肘板A", parameter="孔边距",
        value=8, unit="mm", raw_text="孔边距为 8 mm",
    )[0]
    return EngineeringGraph().reduce([event])


def _design_store():
    store = DesignStateStore()
    operation = GraphOperation("add_node", "node:panel-thickness", {
        "uid": "node:panel-thickness", "view": "parameter_rule", "node_type": "ParameterValue",
        "state": "derived", "evidence": [{"locator": "table:unit_area_load_thickness"}],
    })
    proposal = GraphProposal.create("neo4j-design", store.head.version_id, (), (operation.target,), (operation,), (), ("schema", "write_set"))
    store.commit(proposal)
    return store


def test_projection_is_deterministic_parameterized_and_uses_merge_ids():
    graph = _graph()
    first = build_cypher_batches(graph, batch_size=2)
    second = build_cypher_batches(graph, batch_size=2)
    assert first == second
    assert first
    query_text = "\n".join(batch.query for batch in first)
    assert "MERGE (n:EngineeringNode {uid: row.uid})" in query_text
    assert "MERGE (s)-[r:ENGINEERING_RELATION {rid: row.rid}]->(t)" in query_text
    assert "origin" in query_text and "valid_from_event" in query_text and "active" in query_text
    assert "SET n = row.props" in query_text and "SET r = row.props" in query_text
    assert all(set(batch.parameters) == {"rows"} for batch in first)
    assert "neo4j" not in sys.modules


def test_optional_writer_imports_driver_only_when_explicitly_called(monkeypatch):
    class Session:
        def __init__(self):
            self.calls = []
        def __enter__(self):
            return self
        def __exit__(self, *_):
            return None
        def run(self, query, **parameters):
            self.calls.append((query, parameters))

    class Driver:
        def __init__(self):
            self.session_obj = Session()
        def __enter__(self):
            return self
        def __exit__(self, *_):
            return None
        def session(self, database=None):
            assert database == "neo4j-test"
            return self.session_obj

    driver = Driver()
    class GraphDatabase:
        @staticmethod
        def driver(uri, auth):
            assert uri == "bolt://example.invalid"
            assert auth == ("user", "secret")
            return driver

    monkeypatch.setitem(sys.modules, "neo4j", type("Neo4j", (), {"GraphDatabase": GraphDatabase}))
    batches = build_cypher_batches(_graph(), batch_size=100)
    count = write_cypher_batches(
        batches, uri="bolt://example.invalid", user="user", password="secret",
        database="neo4j-test",
    )
    assert count == len(batches)
    assert len(driver.session_obj.calls) == len(batches)


def test_design_state_projection_uses_view_labels_and_never_mutates_store():
    store = _design_store()
    before = store.head.graph_hash

    batches = build_design_state_cypher_batches(store)

    assert any(":ParameterRule" in batch.query for batch in batches)
    rows = [row for batch in batches for row in batch.parameters["rows"]]
    assert any(row.get("version_id") == store.head.version_id for row in rows)
    assert any(row.get("state") == "derived" for row in rows)
    assert store.head.graph_hash == before
