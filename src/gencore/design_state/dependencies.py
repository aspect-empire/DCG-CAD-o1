"""Deterministic typed dependency traversal for local recomputation."""

from __future__ import annotations

from collections import deque
from collections.abc import Mapping, Set
from dataclasses import dataclass


@dataclass(frozen=True)
class DependencyEdge:
    source: str
    target: str
    relation: str
    confidence: float

    def __post_init__(self) -> None:
        if not self.source or not self.target or not self.relation:
            raise ValueError("dependency edge fields must be non-empty")
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("dependency confidence must be between 0 and 1")


@dataclass(frozen=True)
class ImpactPath:
    start: str
    target: str
    node_uids: tuple[str, ...]
    relations: tuple[str, ...]
    confidence: float


@dataclass(frozen=True)
class AffectedSubgraph:
    node_uids: tuple[str, ...]
    paths: tuple[ImpactPath, ...]
    protected_boundaries: tuple[str, ...]


def affected_subgraph(
    edges: tuple[DependencyEdge, ...] | list[DependencyEdge],
    *,
    starts: Set[str] | set[str],
    allowed_relations: Set[str] | set[str],
    max_depth: int,
    protected: Set[str] | set[str] = frozenset(),
) -> AffectedSubgraph:
    if max_depth < 0:
        raise ValueError("max_depth cannot be negative")
    start_set = {str(item) for item in starts}
    allowed = {str(item) for item in allowed_relations}
    protected_set = {str(item) for item in protected}
    adjacency: dict[str, list[DependencyEdge]] = {}
    for edge in sorted(edges, key=lambda item: (item.source, item.target, item.relation)):
        if edge.relation in allowed:
            adjacency.setdefault(edge.source, []).append(edge)

    seen = set(start_set)
    boundaries: set[str] = set()
    paths: dict[str, ImpactPath] = {}
    queue = deque(
        (start, (start,), (), 1.0, 0) for start in sorted(start_set)
    )
    while queue:
        current, nodes, relations, confidence, depth = queue.popleft()
        if depth >= max_depth:
            continue
        for edge in adjacency.get(current, ()):
            if edge.target in protected_set and edge.target not in start_set:
                boundaries.add(edge.target)
                continue
            if edge.target in seen:
                continue
            seen.add(edge.target)
            next_nodes = (*nodes, edge.target)
            next_relations = (*relations, edge.relation)
            next_confidence = confidence * float(edge.confidence)
            paths[edge.target] = ImpactPath(
                start=nodes[0],
                target=edge.target,
                node_uids=next_nodes,
                relations=next_relations,
                confidence=next_confidence,
            )
            queue.append(
                (
                    edge.target,
                    next_nodes,
                    next_relations,
                    next_confidence,
                    depth + 1,
                )
            )

    return AffectedSubgraph(
        node_uids=tuple(sorted(seen)),
        paths=tuple(
            sorted(
                paths.values(),
                key=lambda item: (
                    len(item.relations),
                    item.start,
                    item.target,
                    item.relations,
                ),
            )
        ),
        protected_boundaries=tuple(sorted(boundaries)),
    )


def affected_closure(
    dependencies: Mapping[str, Set[str]], starts: Set[str]
) -> set[str]:
    """Compatibility wrapper for the original untyped closure."""
    edges = tuple(
        DependencyEdge(source, target, "depends_on", 1.0)
        for source in sorted(dependencies)
        for target in sorted(dependencies[source])
    )
    result = affected_subgraph(
        edges,
        starts=starts,
        allowed_relations={"depends_on"},
        max_depth=max(1, len(edges) + len(starts)),
    )
    return set(result.node_uids)


__all__ = [
    "AffectedSubgraph",
    "DependencyEdge",
    "ImpactPath",
    "affected_closure",
    "affected_subgraph",
]
