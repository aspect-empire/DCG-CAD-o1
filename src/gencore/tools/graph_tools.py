"""Offline event, graph, reasoner, and Skill-governance wrappers."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from ..adapters import adapt_base_pipeline, adapt_cad_report, adapt_text_assertion
from ..event_store import JsonlEventStore
from ..events import EngineeringEvent
from ..graph import EngineeringGraph
from ..reasoner import GraphReasoner
from ..skill_governance import CandidateEvidence, SkillGovernance
from ..tool_registry import ToolSpec
from ..workspace import WorkspaceLayout, authoritative_workspace


OBJECT_SCHEMA = {"type": "object"}


def _events(payload: dict[str, Any]) -> list[EngineeringEvent]:
    raw = payload.get("events")
    if not isinstance(raw, list):
        raise ValueError("events must be a list")
    return [EngineeringEvent.from_dict(item) for item in raw]


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _workspace(payload: dict[str, Any], workspace_root: str | Path | None) -> WorkspaceLayout:
    return authoritative_workspace(payload, project_root=_project_root(), workspace_root=workspace_root)


def ingest(payload: dict[str, Any], *, workspace_root: str | Path | None = None) -> dict[str, Any]:
    kind = payload.get("kind")
    run_id = str(payload.get("run_id") or "")
    body = payload.get("payload")
    if not run_id or not isinstance(body, dict):
        raise ValueError("run_id and dict payload are required")
    common = {key: payload[key] for key in ("path", "sequence_start", "occurred_at") if key in payload}
    if kind == "text":
        events = adapt_text_assertion(run_id=run_id, **body, **common)
    elif kind == "base":
        events = adapt_base_pipeline(body, run_id=run_id, **common)
    elif kind == "cad":
        events = adapt_cad_report(body, run_id=run_id, **common)
    else:
        raise ValueError("kind must be text, base, or cad")
    written = 0
    store_path = payload.get("event_store_path")
    if store_path is not None:
        layout = _workspace(payload, workspace_root)
        written = JsonlEventStore(layout.resolve(store_path)).replay(events)
    return {"events": [event.to_dict() for event in events], "events_written": written}


def _build(payload: dict[str, Any]) -> tuple[EngineeringGraph, list[dict[str, Any]]]:
    graph = EngineeringGraph().reduce(_events(payload))
    fusion = GraphReasoner(graph).fuse_parameters()
    return graph, fusion


def _graph_json(graph: EngineeringGraph) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    nodes = [{"uid": uid, **dict(data)} for uid, data in sorted(graph.graph.nodes(data=True))]
    edges = [
        {"source": source, "target": target, "key": key, **dict(data)}
        for source, target, key, data in sorted(graph.graph.edges(keys=True, data=True))
    ]
    return nodes, edges


def build_graph(payload: dict[str, Any]) -> dict[str, Any]:
    graph, fusion = _build(payload)
    nodes, edges = _graph_json(graph)
    return {"graph_hash": graph.graph_hash(), "nodes": nodes, "edges": edges, "parameter_fusion": fusion}


def query_affected(payload: dict[str, Any]) -> dict[str, Any]:
    graph, _ = _build(payload)
    start = payload.get("start_uid")
    if not isinstance(start, str):
        raise ValueError("start_uid is required")
    max_depth = payload.get("max_depth")
    uids = sorted(GraphReasoner(graph).affected_subgraph(start, max_depth=max_depth))
    return {"start_uid": start, "node_uids": uids}


def evaluate_candidate(payload: dict[str, Any]) -> dict[str, Any]:
    raw = payload.get("evidence")
    if not isinstance(raw, list):
        raise ValueError("evidence must be a list")
    decision = SkillGovernance().evaluate(CandidateEvidence(**item) for item in raw)
    return {**asdict(decision), "requires_human_confirmation": True}


def graph_tool_specs(*, workspace_root: str | Path | None = None) -> list[ToolSpec]:
    return [
        ToolSpec("graph.ingest", "Normalize text, base-pipeline, or CAD payloads into events.", OBJECT_SCHEMA, OBJECT_SCHEMA, "workspace_write", "offline", lambda payload: ingest(payload, workspace_root=workspace_root)),
        ToolSpec("graph.build", "Build and replay a deterministic engineering graph from events.", OBJECT_SCHEMA, OBJECT_SCHEMA, "read_only", "offline", build_graph),
        ToolSpec("graph.query_affected", "Query the affected graph neighborhood for an entity.", OBJECT_SCHEMA, OBJECT_SCHEMA, "read_only", "offline", query_affected),
        ToolSpec("skill.evaluate_candidate", "Evaluate candidate Skill evidence without changing formal rules.", OBJECT_SCHEMA, OBJECT_SCHEMA, "read_only", "offline", evaluate_candidate),
    ]
