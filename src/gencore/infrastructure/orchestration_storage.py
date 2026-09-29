"""Workspace implementations for checkpoints, approvals, events, and artifacts."""

from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import uuid
from typing import Any, Mapping

from gencore.events import canonical_hash, canonical_json
from gencore.workspace import WorkspaceLayout


def _validate_run_id(run_id: str) -> str:
    if (
        not isinstance(run_id, str)
        or not run_id
        or run_id in {".", ".."}
        or any(character in run_id for character in ("/", "\\", ":"))
    ):
        raise ValueError("run_id must be one safe path segment")
    return run_id


class WorkspaceOrchestrationStorage:
    def __init__(self, workspace_root: str | Path, *, run_id: str) -> None:
        self.run_id = _validate_run_id(run_id)
        self.layout = WorkspaceLayout(workspace_root, ()).create()
        self.run_root = self.layout.resolve(f"runs/state/{self.run_id}")
        self.run_root.mkdir(parents=True, exist_ok=True)
        self.checkpoint_path = self.run_root / "checkpoints" / "current.json"
        self.event_path = self.run_root / "runtime_events.jsonl"
        self.artifact_root = self.run_root / "artifacts"
        self.artifact_root.mkdir(parents=True, exist_ok=True)

    def save_checkpoint(self, checkpoint: Mapping[str, Any]) -> None:
        if not checkpoint.get("graph_version"):
            raise ValueError("checkpoint graph_version is required")
        self.layout.atomic_write_json(
            f"runs/state/{self.run_id}/checkpoints/current.json",
            dict(checkpoint),
        )

    def load_checkpoint(self) -> dict[str, Any] | None:
        if not self.checkpoint_path.exists():
            return None
        return json.loads(self.checkpoint_path.read_text(encoding="utf-8"))

    def record_approval(self, approval: Mapping[str, Any]) -> dict[str, Any]:
        required = ("operation_id", "graph_version", "decision", "operator")
        missing = [name for name in required if not approval.get(name)]
        if missing:
            raise ValueError("approval requires: " + ", ".join(missing))
        return self.publish(
            {
                "event_type": "approval.decision",
                "run_id": self.run_id,
                "payload": dict(approval),
            }
        )

    def publish(self, event: Mapping[str, Any]) -> dict[str, Any]:
        body = dict(event)
        body.pop("event_id", None)
        body.pop("sequence_no", None)
        body.setdefault("run_id", self.run_id)
        if body["run_id"] != self.run_id:
            raise ValueError("event run_id does not match storage run_id")
        event_id = "evt:" + canonical_hash(body)
        current = self.read_events()
        by_id = {item["event_id"]: item for item in current}
        existing = by_id.get(event_id)
        if existing is not None:
            return existing
        record = {
            "event_id": event_id,
            "sequence_no": len(current) + 1,
            **body,
        }
        if existing is None:
            current.append(record)
            text = "".join(canonical_json(item) + "\n" for item in current)
            self.layout.atomic_write_text(
                f"runs/state/{self.run_id}/runtime_events.jsonl",
                text,
            )
        return record

    def read_events(self) -> list[dict[str, Any]]:
        if not self.event_path.exists():
            return []
        result = []
        for line_no, line in enumerate(
            self.event_path.read_text(encoding="utf-8").splitlines(),
            1,
        ):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid runtime event at JSONL line {line_no}") from exc
            expected = "evt:" + canonical_hash(
                {
                    key: item
                    for key, item in value.items()
                    if key not in {"event_id", "sequence_no"}
                }
            )
            if value.get("event_id") != expected:
                raise ValueError(f"runtime event hash mismatch at JSONL line {line_no}")
            result.append(value)
        return result

    def put_artifact(self, locator: str, content: bytes) -> dict[str, Any]:
        if not isinstance(content, bytes):
            raise TypeError("artifact content must be bytes")
        relative = f"runs/state/{self.run_id}/artifacts/{locator}"
        target = self.layout.resolve(relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
        try:
            temporary.write_bytes(content)
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
        return {
            "locator": relative.replace("\\", "/"),
            "sha256": sha256(content).hexdigest(),
            "size_bytes": len(content),
        }

    def verify_artifact(self, artifact_ref: Mapping[str, Any]) -> bool:
        try:
            path = self.layout.resolve(str(artifact_ref["locator"]))
            expected = str(artifact_ref["sha256"]).lower()
        except (KeyError, TypeError, ValueError):
            return False
        if not path.is_file():
            return False
        return sha256(path.read_bytes()).hexdigest() == expected


__all__ = ["WorkspaceOrchestrationStorage"]
