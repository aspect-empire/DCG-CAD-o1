"""Deterministic NetworkX engineering-graph reduction."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

import networkx as nx

from .events import EngineeringEvent, canonical_hash


NODE_TYPES = frozenset({"Task", "Evidence", "EngineeringEntity", "Parameter", "Constraint", "Rule", "Tool",
                        "SkillVersion", "Execution", "Validation", "FailureSignature", "Fallback", "Artifact",
                        "RegressionSuite", "Evaluation", "PromotionDecision"})
RELATION_TYPES = frozenset({"HAS_ENTITY", "SUPPORTS", "DESCRIBES", "RESTRICTS", "USES", "APPLIES", "INSTANCE_OF",
                            "PRODUCES", "VALIDATES", "TRIGGERS", "HANDLES", "ACTIVATES", "EVALUATED_BY",
                            "SUPERSEDES", "DECIDES", "BASED_ON"})


def node_uid(node_type: str, natural_key: Any) -> str:
    return f"node:{canonical_hash({'node_type': node_type, 'natural_key': natural_key})}"


def edge_uid(source_uid: str, target_uid: str, relation: str, discriminator: Any) -> str:
    return f"edge:{canonical_hash({'source': source_uid, 'target': target_uid, 'relation': relation, 'discriminator': discriminator})}"


class EngineeringGraph:
    def __init__(self, graph: nx.MultiDiGraph | None = None):
        self.graph = graph if graph is not None else nx.MultiDiGraph()
        self._reduced_event_ids: set[str] = set(self.graph.graph.get("reduced_event_ids", ()))

    def _node(self, node_type: str, natural_key: Any, provenance_event_id: str, **attrs: Any) -> str:
        if node_type not in NODE_TYPES:
            raise ValueError(f"unsupported node type {node_type}")
        uid = node_uid(node_type, natural_key)
        if uid not in self.graph:
            self.graph.add_node(uid, node_uid=uid, node_type=node_type, natural_key=natural_key,
                                active=True, valid_from_event=provenance_event_id, valid_to_event=None,
                                premise_event_ids=[provenance_event_id], **attrs)
        else:
            data = self.graph.nodes[uid]
            premises = data.setdefault("premise_event_ids", [])
            if provenance_event_id not in premises:
                premises.append(provenance_event_id)
                premises.sort()
            current_start = data.get("valid_from_event")
            if current_start is None or provenance_event_id < current_start:
                data["valid_from_event"] = provenance_event_id
            for key, value in attrs.items():
                if key not in data or data[key] in (None, ""):
                    data[key] = value
        return uid

    def add_edge(self, source: str, target: str, relation: str, *, origin: str,
                 premise_event_ids: Iterable[str], derived_by: str | None = None,
                 discriminator: Any = None, **attrs: Any) -> str:
        if relation not in RELATION_TYPES:
            raise ValueError(f"unsupported relation {relation}")
        premises = sorted(set(premise_event_ids))
        discriminator = discriminator if discriminator is not None else premises
        uid = edge_uid(source, target, relation, discriminator)
        if not self.graph.has_edge(source, target, key=uid):
            self.graph.add_edge(source, target, key=uid, edge_uid=uid, relation=relation, origin=origin,
                                derived_by=derived_by, premise_event_ids=premises, active=True,
                                valid_from_event=premises[0] if premises else None,
                                valid_to_event=None, **attrs)
        return uid

    def reduce(self, events: Iterable[EngineeringEvent]) -> "EngineeringGraph":
        for event in sorted(events, key=lambda item: item.event_id):
            if event.event_id in self._reduced_event_ids:
                continue
            self._reduce_event(event)
            self._reduced_event_ids.add(event.event_id)
        self.graph.graph["reduced_event_ids"] = sorted(self._reduced_event_ids)
        return self

    def _reduce_event(self, event: EngineeringEvent) -> None:
        # Event payloads are deeply frozen; graph attributes must remain JSON/export serializable.
        payload = event.to_dict()["payload"]
        task = self._node("Task", event.run_id, event.event_id, run_id=event.run_id)
        evidence = self._node("Evidence", event.event_id, event.event_id, event_id=event.event_id,
                              event_type=event.event_type, producer=event.producer,
                              source=event.source.to_dict(), payload=event.to_dict()["payload"])
        self.add_edge(task, evidence, "PRODUCES", origin="observed", premise_event_ids=[event.event_id])

        if event.event_type == "parameter.observed":
            entity_name = payload.get("entity", "未指定实体")
            entity = self._node("EngineeringEntity", [payload.get("entity_type", "EngineeringEntity"), entity_name],
                                event.event_id, name=entity_name, entity_type=payload.get("entity_type", "EngineeringEntity"))
            parameter_name = payload.get("parameter")
            parameter = self._node("Parameter", [entity, parameter_name], event.event_id, name=parameter_name,
                                   entity_uid=entity, observations=[])
            observation = {"event_id": event.event_id, "value": payload.get("value"), "unit": payload.get("unit", ""),
                           "producer": event.producer}
            observations = self.graph.nodes[parameter].setdefault("observations", [])
            if observation not in observations:
                observations.append(observation)
                observations.sort(key=lambda item: item["event_id"])
            self.add_edge(task, entity, "HAS_ENTITY", origin="observed", premise_event_ids=[event.event_id])
            self.add_edge(evidence, parameter, "SUPPORTS", origin="observed", premise_event_ids=[event.event_id])
            self.add_edge(parameter, entity, "DESCRIBES", origin="observed", premise_event_ids=[event.event_id])
        elif event.event_type == "rule.applied":
            node = self._node("Rule", payload.get("rule_id", event.event_id), event.event_id,
                              rule_id=payload.get("rule_id"), status=payload.get("status"))
            self.add_edge(task, node, "APPLIES", origin="observed", premise_event_ids=[event.event_id])
        elif event.event_type == "tool.used":
            node = self._node("Tool", payload.get("tool", event.event_id), event.event_id,
                              name=payload.get("tool"), status=payload.get("status"))
            self.add_edge(task, node, "USES", origin="observed", premise_event_ids=[event.event_id])
        elif event.event_type == "execution.completed":
            node = self._node("Execution", event.event_id, event.event_id, **payload)
            self.add_edge(task, node, "PRODUCES", origin="observed", premise_event_ids=[event.event_id])
        elif event.event_type == "validation.completed":
            node = self._node("Validation", event.event_id, event.event_id, **payload)
            self.add_edge(evidence, node, "VALIDATES", origin="observed", premise_event_ids=[event.event_id])
        elif event.event_type == "failure.observed":
            key = [payload.get("raw_error_code", "UNKNOWN"), payload.get("message", "")]
            node = self._node("FailureSignature", key, event.event_id, **payload)
            self.add_edge(evidence, node, "TRIGGERS", origin="observed", premise_event_ids=[event.event_id])
        elif event.event_type == "fallback.activated":
            node = self._node("Fallback", [payload.get("requested_mode"), payload.get("actual_mode")], event.event_id, **payload)
            self.add_edge(evidence, node, "ACTIVATES", origin="observed", premise_event_ids=[event.event_id])
        elif event.event_type == "artifact.produced":
            artifact = payload.get("artifact", {})
            key = artifact.get("artifact_id") or artifact.get("path") or event.event_id
            node = self._node("Artifact", key, event.event_id, **payload)
            self.add_edge(task, node, "PRODUCES", origin="observed", premise_event_ids=[event.event_id])

    def deactivate_node(self, uid: str, closing_event_id: str) -> None:
        self.graph.nodes[uid]["active"] = False
        self.graph.nodes[uid]["valid_to_event"] = closing_event_id

    def graph_hash(self) -> str:
        nodes = [{"uid": uid, **dict(data)} for uid, data in sorted(self.graph.nodes(data=True))]
        edges = [{"source": source, "target": target, "key": key, **dict(data)}
                 for source, target, key, data in sorted(self.graph.edges(keys=True, data=True))]
        return canonical_hash({"nodes": nodes, "edges": edges})


GraphReducer = EngineeringGraph
