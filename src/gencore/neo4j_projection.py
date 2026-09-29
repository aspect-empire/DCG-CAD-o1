"""Pure, deterministic Neo4j projection batches with an explicit optional writer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .events import canonical_json
from .graph import EngineeringGraph
from .design_state.versions import DesignStateStore


@dataclass(frozen=True)
class CypherBatch:
    query: str
    parameters: Mapping[str, Any]


NODE_QUERY = """UNWIND $rows AS row
MERGE (n:EngineeringNode {uid: row.uid})
SET n = row.props,
    n.uid = row.uid,
    n.node_type = row.node_type,
    n.active = row.active,
    n.valid_from_event = row.valid_from_event,
    n.valid_to_event = row.valid_to_event"""

EDGE_QUERY = """UNWIND $rows AS row
MATCH (s:EngineeringNode {uid: row.source})
MATCH (t:EngineeringNode {uid: row.target})
MERGE (s)-[r:ENGINEERING_RELATION {rid: row.rid}]->(t)
SET r = row.props,
    r.rid = row.rid,
    r.relation = row.relation,
    r.origin = row.origin,
    r.active = row.active,
    r.valid_from_event = row.valid_from_event,
    r.valid_to_event = row.valid_to_event"""

VIEW_LABELS = {
    "intent_requirement": "IntentRequirement",
    "product_function": "ProductFunction",
    "parameter_rule": "ParameterRule",
    "geometry_spatial": "GeometrySpatial",
    "process_tool": "ProcessTool",
    "result_evidence": "ResultEvidence",
}

DESIGN_EDGE_QUERY = """UNWIND $rows AS row
MATCH (s:EngineeringNode {uid: row.source})
MATCH (t:EngineeringNode {uid: row.target})
MERGE (s)-[r:DESIGN_RELATION {rid: row.rid, version_id: row.version_id}]->(t)
SET r += row.props,
    r.relation = row.relation,
    r.state = row.state"""


def _property(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return canonical_json(value)


def _props(data: Mapping[str, Any], excluded: set[str]) -> dict[str, Any]:
    return {key: _property(value) for key, value in sorted(data.items()) if key not in excluded}


def _chunks(rows: list[dict[str, Any]], size: int) -> Iterable[list[dict[str, Any]]]:
    for start in range(0, len(rows), size):
        yield rows[start:start + size]


def build_cypher_batches(graph: EngineeringGraph, *, batch_size: int = 500) -> list[CypherBatch]:
    """Generate Cypher without importing a driver or connecting to a database."""
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    node_rows = []
    for uid, data in sorted(graph.graph.nodes(data=True)):
        node_rows.append({
            "uid": uid, "node_type": data.get("node_type"), "active": bool(data.get("active", True)),
            "valid_from_event": data.get("valid_from_event"), "valid_to_event": data.get("valid_to_event"),
            "props": _props(data, {"node_uid", "node_type", "active", "valid_from_event", "valid_to_event"}),
        })
    edge_rows = []
    for source, target, rid, data in sorted(graph.graph.edges(keys=True, data=True)):
        edge_rows.append({
            "rid": rid, "source": source, "target": target, "relation": data.get("relation"),
            "origin": data.get("origin"), "active": bool(data.get("active", True)),
            "valid_from_event": data.get("valid_from_event"), "valid_to_event": data.get("valid_to_event"),
            "props": _props(data, {"edge_uid", "relation", "origin", "active", "valid_from_event", "valid_to_event"}),
        })
    batches = [CypherBatch(NODE_QUERY, {"rows": rows}) for rows in _chunks(node_rows, batch_size)]
    batches.extend(CypherBatch(EDGE_QUERY, {"rows": rows}) for rows in _chunks(edge_rows, batch_size))
    return batches


def build_design_state_cypher_batches(
    store: DesignStateStore,
    *,
    version_id: str | None = None,
    batch_size: int = 500,
) -> list[CypherBatch]:
    """Project one design-state snapshot without connecting to Neo4j."""
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    selected_version = version_id or store.head.version_id
    snapshot = store.snapshot(selected_version)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for uid, data in sorted(snapshot["nodes"].items()):
        view = str(data.get("view"))
        if view not in VIEW_LABELS:
            raise ValueError(f"unsupported design-state view: {view}")
        grouped.setdefault(view, []).append({
            "uid": uid,
            "version_id": selected_version,
            "node_type": data.get("node_type"),
            "state": data.get("state"),
            "evidence": _property(data.get("evidence", [])),
            "props": _props(data, {"uid", "node_type", "state", "evidence"}),
        })
    batches: list[CypherBatch] = []
    for view in sorted(grouped):
        label = VIEW_LABELS[view]
        query = f"""UNWIND $rows AS row
MERGE (n:EngineeringNode:{label} {{uid: row.uid, version_id: row.version_id}})
SET n += row.props,
    n.node_type = row.node_type,
    n.state = row.state,
    n.evidence = row.evidence"""
        batches.extend(CypherBatch(query, {"rows": rows}) for rows in _chunks(grouped[view], batch_size))
    edge_rows = [
        {
            "rid": uid,
            "source": data.get("source"),
            "target": data.get("target"),
            "version_id": selected_version,
            "relation": data.get("relation"),
            "state": data.get("state"),
            "props": _props(data, {"uid", "source", "target", "relation", "state"}),
        }
        for uid, data in sorted(snapshot["edges"].items())
    ]
    batches.extend(CypherBatch(DESIGN_EDGE_QUERY, {"rows": rows}) for rows in _chunks(edge_rows, batch_size))
    return batches


def write_cypher_batches(batches: Iterable[CypherBatch], *, uri: str, user: str,
                         password: str, database: str | None = None) -> int:
    """Write explicitly supplied batches; credentials are mandatory and have no defaults."""
    if not uri or not user or not password:
        raise ValueError("uri, user and password are required")
    from neo4j import GraphDatabase  # type: ignore[import-not-found]

    count = 0
    with GraphDatabase.driver(uri, auth=(user, password)) as driver:
        with driver.session(database=database) as session:
            for batch in batches:
                session.run(batch.query, **dict(batch.parameters))
                count += 1
    return count


__all__ = ["CypherBatch", "build_cypher_batches", "build_design_state_cypher_batches", "write_cypher_batches"]
