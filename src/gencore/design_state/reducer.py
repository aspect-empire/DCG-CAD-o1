"""Pure reduction of graph operations into a new design-state snapshot."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from gencore.events import canonical_json

from .proposals import GraphOperation
from .records import _thaw


def _record_bucket(graph: dict[str, dict[str, Any]], target: str) -> dict[str, Any]:
    if target in graph["nodes"]:
        return graph["nodes"]
    if target in graph["edges"]:
        return graph["edges"]
    raise ValueError(f"graph target does not exist: {target}")


def _add_record(bucket: dict[str, Any], operation: GraphOperation) -> None:
    value = _thaw(operation.value)
    if value.get("uid", operation.target) != operation.target:
        raise ValueError(f"record uid does not match operation target: {operation.target}")
    value["uid"] = operation.target
    existing = bucket.get(operation.target)
    if existing is not None and canonical_json(existing) != canonical_json(value):
        raise ValueError(f"conflicting graph record: {operation.target}")
    bucket[operation.target] = value


def reduce_operations(snapshot: Mapping[str, Any], operations: Iterable[GraphOperation]) -> dict[str, Any]:
    graph = _thaw(snapshot)
    graph.setdefault("nodes", {})
    graph.setdefault("edges", {})
    for operation in operations:
        if operation.kind == "add_node":
            _add_record(graph["nodes"], operation)
        elif operation.kind == "add_edge":
            _add_record(graph["edges"], operation)
        elif operation.kind == "set_node_state":
            if operation.target not in graph["nodes"]:
                raise ValueError(f"graph target does not exist: {operation.target}")
            value = _thaw(operation.value)
            graph["nodes"][operation.target]["state"] = value["state"]
            for key in ("invalidated_by", "state_reason"):
                if key in value:
                    graph["nodes"][operation.target][key] = value[key]
        elif operation.kind == "supersede_node":
            if operation.target not in graph["nodes"]:
                raise ValueError(f"graph target does not exist: {operation.target}")
            value = _thaw(operation.value)
            graph["nodes"][operation.target]["state"] = "superseded"
            graph["nodes"][operation.target]["valid_to_event"] = value["closing_event_id"]
        elif operation.kind == "bind_evidence":
            bucket = _record_bucket(graph, operation.target)
            record = bucket[operation.target]
            evidence = _thaw(operation.value).get("evidence", [])
            current = record.setdefault("evidence", [])
            known = {canonical_json(item) for item in current}
            for item in evidence:
                if canonical_json(item) not in known:
                    current.append(item)
                    known.add(canonical_json(item))
            current.sort(key=canonical_json)
        elif operation.kind == "update_attributes":
            bucket = _record_bucket(graph, operation.target)
            record = bucket[operation.target]
            attributes = _thaw(operation.value).get("attributes")
            if not isinstance(attributes, dict):
                raise ValueError("update_attributes requires an attributes object")
            record.setdefault("attributes", {}).update(attributes)
        elif operation.kind == "bind_reference":
            bucket = _record_bucket(graph, operation.target)
            reference = _thaw(operation.value).get("reference")
            if not isinstance(reference, dict):
                raise ValueError("bind_reference requires a reference object")
            bucket[operation.target]["geometry_reference"] = reference
        else:
            raise ValueError(f"unsupported graph operation: {operation.kind}")
    return graph
