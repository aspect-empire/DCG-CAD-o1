"""Deterministic offline engineering-graph exporters."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import networkx as nx

from .events import canonical_hash, canonical_json
from .graph import EngineeringGraph
from .design_state.versions import DesignStateStore


def node_link_data(graph: EngineeringGraph) -> dict[str, Any]:
    nodes = [{"id": uid, **dict(data)} for uid, data in sorted(graph.graph.nodes(data=True))]
    links = [{"source": source, "target": target, "key": key, **dict(data)}
             for source, target, key, data in sorted(graph.graph.edges(keys=True, data=True))]
    return {"directed": True, "multigraph": True, "graph": {}, "nodes": nodes, "links": links}


def _scalar(value: Any) -> str | int | float | bool:
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return value
    return canonical_json(value)


def _graphml_copy(graph: EngineeringGraph) -> nx.MultiDiGraph:
    exported = nx.MultiDiGraph()
    for uid, data in sorted(graph.graph.nodes(data=True)):
        exported.add_node(uid, **{key: _scalar(value) for key, value in sorted(data.items())})
    for source, target, key, data in sorted(graph.graph.edges(keys=True, data=True)):
        exported.add_edge(source, target, key=key, **{name: _scalar(value) for name, value in sorted(data.items())})
    return exported


def _mermaid(graph: EngineeringGraph) -> str:
    aliases = {uid: f"n{index}" for index, (uid, _) in enumerate(sorted(graph.graph.nodes(data=True)))}
    lines = ["flowchart LR"]
    for uid, data in sorted(graph.graph.nodes(data=True)):
        label = str(data.get("name") or data.get("node_type") or uid).replace('"', "'")
        lines.append(f'  {aliases[uid]}["{label}"]')
    for source, target, key, data in sorted(graph.graph.edges(keys=True, data=True)):
        lines.append(f'  {aliases[source]} -->|"{data.get("relation", "")}"| {aliases[target]}')
    return "\n".join(lines) + "\n"


def _draw(graph: EngineeringGraph, svg_path: Path, png_path: Path, *, seed: int) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    simple = nx.DiGraph()
    simple.add_nodes_from(sorted(graph.graph.nodes))
    simple.add_edges_from(sorted((source, target) for source, target in graph.graph.edges()))
    positions = nx.spring_layout(simple, seed=seed) if simple.number_of_nodes() > 1 else {next(iter(simple.nodes)): (0.0, 0.0)}
    labels = {uid: data.get("node_type", "Node") for uid, data in graph.graph.nodes(data=True)}
    with matplotlib.rc_context({"svg.hashsalt": "gencore-fixed"}):
        figure, axis = plt.subplots(figsize=(12, 8), dpi=100)
        nx.draw_networkx(simple, pos=positions, labels=labels, ax=axis, node_size=1250,
                         font_size=6, arrows=True, width=0.7)
        axis.set_axis_off()
        figure.tight_layout()
        figure.savefig(svg_path, format="svg", metadata={"Date": None})
        figure.savefig(png_path, format="png", metadata={"Software": "GenCore"})
        plt.close(figure)


def export_graph(graph: EngineeringGraph, output_dir: str | Path, *, seed: int = 20260716) -> list[Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    paths = [output / name for name in ("graph.json", "graph.graphml", "graph.mmd", "graph.svg", "graph.png")]
    paths[0].write_text(json.dumps(node_link_data(graph), ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    nx.write_graphml(_graphml_copy(graph), paths[1], encoding="utf-8", prettyprint=True, infer_numeric_types=True)
    paths[2].write_text(_mermaid(graph), encoding="utf-8", newline="\n")
    _draw(graph, paths[3], paths[4], seed=seed)
    return paths


def export_design_version(
    store: DesignStateStore,
    version_id: str,
    output_dir: str | Path,
) -> Path:
    """Write one immutable design-state version as canonical JSON."""
    snapshot = store.snapshot(version_id)
    version = next(
        (item.version for item in store.events if item.version.version_id == version_id),
        store.head if store.head.version_id == version_id else None,
    )
    graph_hash = version.graph_hash if version is not None else canonical_hash(snapshot)
    payload = {
        "version_id": version_id,
        "graph_hash": graph_hash,
        "nodes": [snapshot["nodes"][uid] for uid in sorted(snapshot["nodes"])],
        "edges": [snapshot["edges"][uid] for uid in sorted(snapshot["edges"])],
    }
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    path = output / f"{version_id.replace(':', '_')}.json"
    path.write_text(canonical_json(payload) + "\n", encoding="utf-8", newline="\n")
    return path


__all__ = ["export_design_version", "export_graph", "node_link_data"]
