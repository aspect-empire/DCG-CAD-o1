"""Workspace-backed persistence for versioned design state and execution packages."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from gencore.design_state import (
    DesignStateStore,
    GraphProposal,
    GraphVersion,
    VersionEvent,
)
from gencore.events import canonical_json
from gencore.workspace import WorkspaceLayout

from .contracts import DesignExecutionPackage


def _validate_run_id(run_id: str) -> str:
    if (
        not isinstance(run_id, str)
        or not run_id
        or run_id in {".", ".."}
        or any(character in run_id for character in ("/", "\\", ":"))
    ):
        raise ValueError("run_id must be one safe path segment")
    return run_id


class WorkspaceStateRepository:
    def __init__(self, workspace_root: str | Path, *, run_id: str) -> None:
        self.run_id = _validate_run_id(run_id)
        self.layout = WorkspaceLayout(workspace_root, ()).create()
        self.run_root = self.layout.resolve(f"runs/state/{self.run_id}")
        self.run_root.mkdir(parents=True, exist_ok=True)
        self.events_path = self.run_root / "events.jsonl"
        self.head_path = self.run_root / "head.json"
        self.packages_root = self.run_root / "packages"
        self.packages_root.mkdir(parents=True, exist_ok=True)
        self._store = DesignStateStore.from_events(self._read_events())
        self.genesis_version = next(iter(self._store.snapshots))
        self._verify_persisted_head()

    @property
    def head(self) -> GraphVersion:
        return self._store.head

    @property
    def snapshots(self):
        return self._store.snapshots

    @property
    def events(self):
        return self._store.events

    def read_snapshot(self, version_id: str | None = None) -> dict:
        return self._store.snapshot(version_id)

    def snapshot(self, version_id: str | None = None) -> dict:
        return self.read_snapshot(version_id)

    def changes_since(self, base_version: str) -> set[str]:
        if base_version == self.head.version_id:
            return set()
        if base_version not in self.snapshots:
            raise ValueError(f"unknown base version: {base_version}")
        committed = {
            event.version.version_id: event
            for event in self.events
            if event.kind == "proposal.committed"
        }
        cursor = self.head.version_id
        changed: set[str] = set()
        while cursor != base_version:
            try:
                event = committed[cursor]
            except KeyError as exc:
                raise ValueError(
                    f"base version is not an ancestor of the active head: {base_version}"
                ) from exc
            changed.update(event.proposal.write_set)
            cursor = event.version.parent_version or ""
        return changed

    def commit(self, proposal: GraphProposal) -> GraphVersion:
        return self._persist_candidate(lambda store: store.commit(proposal))

    def reject(self, proposal: GraphProposal, reason: str) -> GraphVersion:
        return self._persist_candidate(lambda store: store.reject(proposal, reason))

    def save_package(self, package: DesignExecutionPackage) -> Path:
        if package.run_id != self.run_id:
            raise ValueError("execution package run_id does not match repository run_id")
        if package.graph_version not in self.snapshots:
            raise ValueError(f"execution package has unknown graph version: {package.graph_version}")
        name = package.package_id.replace(":", "_") + ".json"
        relative = f"runs/state/{self.run_id}/packages/{name}"
        path = self.layout.atomic_write_json(relative, package.to_dict())
        self.layout.atomic_write_json(
            f"runs/state/{self.run_id}/current_package.json",
            {"package_id": package.package_id, "relative_path": relative},
        )
        return path

    def load_current_package(self, run_id: str | None = None) -> DesignExecutionPackage:
        if run_id is not None and run_id != self.run_id:
            raise ValueError("requested run_id does not match repository run_id")
        pointer = self.run_root / "current_package.json"
        if not pointer.exists():
            raise FileNotFoundError(f"no current execution package for run: {self.run_id}")
        value = json.loads(pointer.read_text(encoding="utf-8"))
        path = self.layout.resolve(value["relative_path"])
        return DesignExecutionPackage.from_dict(
            json.loads(path.read_text(encoding="utf-8"))
        )

    def _persist_candidate(
        self,
        operation: Callable[[DesignStateStore], GraphVersion],
    ) -> GraphVersion:
        candidate = DesignStateStore.from_events(self._store.events)
        result = operation(candidate)
        verified = DesignStateStore.from_events(candidate.events)
        if verified.head != candidate.head:
            raise ValueError("candidate design state did not replay to the same head")
        text = "".join(
            canonical_json(event.to_dict()) + "\n" for event in candidate.events
        )
        self.layout.atomic_write_text(
            f"runs/state/{self.run_id}/events.jsonl",
            text,
        )
        self.layout.atomic_write_json(
            f"runs/state/{self.run_id}/head.json",
            candidate.head.to_dict(),
        )
        self._store = candidate
        return result

    def _read_events(self) -> list[VersionEvent]:
        if not self.events_path.exists():
            return []
        result = []
        for line_no, line in enumerate(
            self.events_path.read_text(encoding="utf-8").splitlines(),
            1,
        ):
            if not line.strip():
                continue
            try:
                result.append(VersionEvent.from_dict(json.loads(line)))
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                raise ValueError(f"invalid version event at JSONL line {line_no}") from exc
        return result

    def _verify_persisted_head(self) -> None:
        if not self.head_path.exists():
            return
        try:
            persisted = GraphVersion.from_dict(
                json.loads(self.head_path.read_text(encoding="utf-8"))
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError("invalid persisted design-state head") from exc
        if persisted != self._store.head:
            raise ValueError("persisted head does not match replayed version events")


__all__ = ["WorkspaceStateRepository"]
