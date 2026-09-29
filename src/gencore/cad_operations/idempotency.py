"""Atomic on-disk idempotency ledger for external CAD calls."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Mapping

from gencore.events import canonical_hash, canonical_json


_SAFE_RUN_ID = re.compile(r"^[A-Za-z0-9._-]+$")
_KEY = re.compile(r"^idem:[0-9a-f]{64}$")


class IdempotencyLedger:
    def __init__(self, workspace_root: str | Path, *, run_id: str = "default") -> None:
        if not _SAFE_RUN_ID.fullmatch(str(run_id)):
            raise ValueError("run_id must be a safe path segment")
        self.directory = (
            Path(workspace_root)
            / "runs"
            / "state"
            / str(run_id)
            / "cad_operations"
        )
        self.directory.mkdir(parents=True, exist_ok=True)

    def _path(self, idempotency_key: str) -> Path:
        if not _KEY.fullmatch(str(idempotency_key)):
            raise ValueError("idempotency key must be idem:<sha256>")
        return self.directory / f"{idempotency_key.removeprefix('idem:')}.json"

    def lookup(self, idempotency_key: str) -> dict[str, Any] | None:
        path = self._path(idempotency_key)
        if not path.exists():
            return None
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("idempotency_key") != idempotency_key:
            raise ValueError("idempotency ledger key mismatch")
        supplied_hash = record.pop("record_hash", None)
        expected_hash = canonical_hash(record)
        record["record_hash"] = supplied_hash
        if supplied_hash != expected_hash:
            raise ValueError("idempotency ledger content hash mismatch")
        return record

    def record(
        self, idempotency_key: str, result: Mapping[str, Any]
    ) -> dict[str, Any]:
        path = self._path(idempotency_key)
        body = {"idempotency_key": idempotency_key, **dict(result)}
        body["record_hash"] = canonical_hash(body)
        existing = self.lookup(idempotency_key)
        if existing is not None:
            if existing != body:
                raise ValueError("conflicting idempotency ledger rewrite")
            return existing

        handle, temporary = tempfile.mkstemp(
            prefix=path.stem + ".", suffix=".tmp", dir=str(self.directory)
        )
        try:
            with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(canonical_json(body))
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return body


__all__ = ["IdempotencyLedger"]
