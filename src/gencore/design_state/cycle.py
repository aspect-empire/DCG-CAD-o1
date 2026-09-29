"""Deterministic orchestration and replay of multimodal design-cycle fixtures."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

from gencore.events import canonical_json
from gencore.foundation_rules import FoundationCalculator, load_default_package

from .adapters import (
    CaseMatchingAdapter,
    CatiaPipelineAdapter,
    InterferenceAdapter,
    ParameterResultAdapter,
    RulePackageAdapter,
    SceneAdapter,
)
from .dependencies import affected_closure
from .proposals import GraphOperation, GraphProposal
from .validator import ProposalConflict, ProposalValidator
from .versions import DesignStateStore, GraphVersion


@dataclass(frozen=True)
class CycleResult:
    scenario_id: str
    stage_states: tuple[str, ...]
    version_count: int
    failed_attempt_count: int
    recomputed_uids: tuple[str, ...]
    unproven_active_values: tuple[str, ...]
    final_version_id: str
    final_graph_hash: str

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        for key in ("stage_states", "recomputed_uids", "unproven_active_values"):
            value[key] = list(value[key])
        return value


class DesignCycle:
    def __init__(self, store: DesignStateStore | None = None):
        self.store = store or DesignStateStore()
        self.genesis_version = self.store.head.version_id
        self.versions: list[GraphVersion] = [self.store.head]
        self._commits: list[tuple[str, str, tuple[str, ...]]] = []

    def _changes_since(self, base_version: str) -> set[str]:
        if base_version == self.store.head.version_id:
            return set()
        changes: set[str] = set()
        cursor = self.store.head.version_id
        for version_id, parent_id, write_set in reversed(self._commits):
            if cursor == base_version:
                break
            if version_id == cursor:
                changes.update(write_set)
                cursor = parent_id
        if cursor != base_version:
            return {uid for _, _, writes in self._commits for uid in writes}
        return changes

    def apply(self, proposal: GraphProposal) -> GraphVersion:
        try:
            ProposalValidator(self.store.head.version_id, self._changes_since(proposal.base_version)).validate(proposal)
            parent = self.store.head.version_id
            version = self.store.commit(proposal)
        except (ProposalConflict, ValueError) as error:
            return self.store.reject(proposal, str(error))
        self.versions.append(version)
        self._commits.append((version.version_id, parent, proposal.write_set))
        return version


def _seed_proposal(run_id: str, base_version: str, nodes: list[Mapping[str, Any]]) -> GraphProposal:
    operations = tuple(GraphOperation("add_node", str(node["uid"]), dict(node)) for node in nodes)
    return GraphProposal.create(run_id, base_version, (), tuple(operation.target for operation in operations), operations, (), ("schema", "write_set"))


def _stale_proposal(run_id: str, base_version: str, target: str) -> GraphProposal:
    operation = GraphOperation("set_node_state", target, {"state": "proposed", "state_reason": "stale_revision"})
    return GraphProposal.create(run_id, base_version, (target,), (target,), (operation,), (), ("schema", "write_set"))


def _unproven_values(snapshot: Mapping[str, Any]) -> tuple[str, ...]:
    unproven = []
    for uid, node in snapshot["nodes"].items():
        if node.get("node_type") != "ParameterValue" or node.get("state") not in {"derived", "verified"}:
            continue
        attributes = node.get("attributes", {})
        if not attributes.get("rule_ids") or not node.get("evidence"):
            unproven.append(uid)
    return tuple(sorted(unproven))


def _write_exports(cycle: DesignCycle, result: CycleResult, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    versions_dir = output_dir / "versions"
    versions_dir.mkdir(parents=True, exist_ok=True)
    event_text = "".join(canonical_json(event.to_dict()) + "\n" for event in cycle.store.events)
    (output_dir / "events.jsonl").write_text(event_text, encoding="utf-8")
    for version in cycle.versions:
        payload = {"version_id": version.version_id, "graph_hash": version.graph_hash, **cycle.store.snapshot(version.version_id)}
        name = version.version_id.replace(":", "_") + ".json"
        (versions_dir / name).write_text(canonical_json(payload), encoding="utf-8")
    snapshot = cycle.store.snapshot()
    artifacts = [node for _, node in sorted(snapshot["nodes"].items()) if node.get("node_type") == "Artifact"]
    (output_dir / "artifacts.json").write_text(canonical_json({"artifacts": artifacts}), encoding="utf-8")
    (output_dir / "summary.json").write_text(canonical_json(result.to_dict()), encoding="utf-8")


def replay_fixture(fixture_path: Path, output_dir: Path) -> CycleResult:
    fixture = json.loads(Path(fixture_path).read_text(encoding="utf-8"))
    run_id = str(fixture["run_id"])
    cycle = DesignCycle()
    stage_states: list[str] = []
    recomputed: set[str] = set()
    for step in fixture["steps"]:
        kind = step["kind"]
        payload = dict(step.get("payload", {}))
        payload.setdefault("run_id", run_id)
        if kind == "rules":
            proposal = RulePackageAdapter().adapt(load_default_package(), run_id=run_id, base_version=cycle.store.head.version_id)
        elif kind == "scene":
            proposal = SceneAdapter().adapt(payload, base_version=cycle.store.head.version_id)
        elif kind == "case_matching":
            proposal = CaseMatchingAdapter().adapt(payload, base_version=cycle.store.head.version_id)
        elif kind == "seed_nodes":
            proposal = _seed_proposal(run_id, cycle.store.head.version_id, step["nodes"])
        elif kind == "stale_attempt":
            base = cycle.genesis_version if step["base_version"] == "genesis" else step["base_version"]
            proposal = _stale_proposal(run_id, base, step["target"])
        elif kind == "calculate":
            calculation = FoundationCalculator().calculate(payload)
            proposal = ParameterResultAdapter().adapt(calculation, run_id=run_id, base_version=cycle.store.head.version_id)
            stage_states.append(calculation.status)
        elif kind == "catia":
            proposal = CatiaPipelineAdapter().adapt(payload, base_version=cycle.store.head.version_id)
            stage_states.append("proposed" if payload.get("status") == "completed" else "rejected")
        elif kind == "interference":
            proposal = InterferenceAdapter().adapt(payload, base_version=cycle.store.head.version_id)
            dependencies = {key: set(value) for key, value in payload.get("dependencies", {}).items()}
            recomputed.update(affected_closure(dependencies, set(payload.get("changed_uids", ()))))
            stage_states.append("verified" if payload.get("status") == "passed" else "conflicted")
        else:
            raise ValueError(f"unsupported fixture step: {kind}")
        cycle.apply(proposal)

    failed_attempts = sum(event.kind == "proposal.rejected" for event in cycle.store.events)
    result = CycleResult(
        str(fixture["scenario_id"]),
        tuple(stage_states),
        len(cycle.versions),
        failed_attempts,
        tuple(sorted(recomputed)),
        _unproven_values(cycle.store.snapshot()),
        cycle.store.head.version_id,
        cycle.store.head.graph_hash,
    )
    _write_exports(cycle, result, Path(output_dir))
    expected_path = Path(fixture_path).with_name("expected_summary.json")
    if expected_path.exists():
        expected = json.loads(expected_path.read_text(encoding="utf-8"))
        actual = result.to_dict()
        for key, value in expected.items():
            if actual.get(key) != value:
                raise AssertionError(f"fixture summary mismatch for {key}: {actual.get(key)!r} != {value!r}")
    return result
