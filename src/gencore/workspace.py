"""Safe shared-workspace paths and atomic filesystem writes."""

from __future__ import annotations

import json
import os
import stat
import uuid
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Iterable, Mapping


ASSET_FIELDS = {
    "source_path",
    "source_id",
    "relative_source_path",
    "target_path",
    "category",
    "asset_type",
    "sha256",
    "size_bytes",
    "state",
    "duplicate_group",
}
ASSET_STATES = {"static", "generated_example", "runtime_seed"}


def _safe_relative(value: str | Path) -> PurePosixPath:
    raw = str(value).replace("\\", "/")
    path = PurePosixPath(raw)
    if (
        not raw
        or path.is_absolute()
        or PureWindowsPath(str(value)).drive
        or any(":" in part for part in path.parts)
        or ".." in path.parts
    ):
        raise ValueError(f"workspace child path must be relative without traversal: {value}")
    return path


class WorkspaceLayout:
    """Resolve and initialize paths confined to one shared workspace root."""

    def __init__(self, root: str | Path, directories: Iterable[str | Path]) -> None:
        self.root = Path(root).absolute()
        self.relative_directories = tuple(
            sorted((_safe_relative(path) for path in directories), key=str)
        )

    @classmethod
    def from_config(
        cls, config_path: str | Path, *, project_root: str | Path | None = None
    ) -> "WorkspaceLayout":
        config_file = Path(config_path)
        config = json.loads(config_file.read_text(encoding="utf-8"))
        if config.get("version") != 1:
            raise ValueError("workspace config version must be 1")
        root_relative = _safe_relative(config.get("root", ""))
        base = (
            Path(project_root).resolve()
            if project_root is not None
            else config_file.resolve().parents[1]
        )
        root = base.joinpath(*root_relative.parts)
        resolved = root.resolve(strict=False)
        if resolved == base or base not in resolved.parents:
            raise ValueError("workspace root must resolve strictly inside project_root")
        return cls(root, config.get("directories", ()))

    def resolve(self, child: str | Path) -> Path:
        relative = _safe_relative(child)
        lexical = self.root.joinpath(*relative.parts)
        current = self.root
        for part in relative.parts:
            if current.exists() and _is_reparse(current):
                raise ValueError(f"workspace refuses link or reparse ancestor: {current}")
            current = current / part
        if current.exists() and _is_reparse(current):
            raise ValueError(f"workspace refuses link or reparse target: {current}")
        resolved_root = self.root.resolve(strict=False)
        resolved = lexical.resolve(strict=False)
        if resolved == resolved_root or resolved_root not in resolved.parents:
            raise ValueError(f"workspace path traversal is not allowed: {child}")
        return resolved

    def create(self) -> "WorkspaceLayout":
        self.root.mkdir(parents=True, exist_ok=True)
        for relative in self.relative_directories:
            self.resolve(relative).mkdir(parents=True, exist_ok=True)
        return self

    def create_run(self, run_id: str) -> dict[str, Path]:
        safe_id = _safe_relative(run_id)
        if len(safe_id.parts) != 1 or safe_id.name in {"", "."}:
            raise ValueError("run_id must be one relative path segment")
        result = {
            kind: self.resolve(f"runs/{kind}/{safe_id.name}")
            for kind in ("inputs", "outputs", "logs", "reports")
        }
        for path in result.values():
            path.mkdir(parents=True, exist_ok=True)
        return result

    def atomic_write_text(self, child: str | Path, content: str) -> Path:
        target = self.resolve(child)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
        try:
            temporary.write_text(content, encoding="utf-8", newline="\n")
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
        return target

    def atomic_write_json(self, child: str | Path, value: Any) -> Path:
        content = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        return self.atomic_write_text(child, content)


def authoritative_workspace(
    payload: Mapping[str, Any], *, project_root: str | Path, workspace_root: str | Path | None = None
) -> WorkspaceLayout:
    """Return the one workspace authorized for a tool registry instance.

    Tool payloads may repeat the configured path for traceability, but cannot
    redirect writes to a caller-chosen directory.  Registry construction (or
    AgentConfig) is the authority boundary; tests may inject an isolated root
    when constructing the registry.
    """
    project = Path(project_root).resolve()
    configured = Path(workspace_root) if workspace_root is not None else project / "workspace"
    configured = configured.absolute()
    requested = payload.get("workspace_root")
    if requested is not None:
        if not isinstance(requested, str) or not requested:
            raise ValueError("workspace_root must be a non-empty string when supplied")
        if Path(requested).absolute().resolve(strict=False) != configured.resolve(strict=False):
            raise ValueError("tool writes are restricted to the configured shared workspace")
    return WorkspaceLayout(configured, ()).create()


def load_asset_manifest(path: str | Path) -> dict[str, Any]:
    """Load and validate the deterministic workspace asset catalog."""
    manifest = json.loads(Path(path).read_text(encoding="utf-8"))
    if manifest.get("version") != 1 or not isinstance(manifest.get("assets"), list):
        raise ValueError("asset manifest requires version 1 and an assets list")
    targets: list[str] = []
    for index, asset in enumerate(manifest["assets"]):
        if set(asset) != ASSET_FIELDS:
            raise ValueError(f"asset {index} has invalid fields")
        _safe_relative(asset["target_path"])
        _safe_relative(asset["relative_source_path"])
        if asset["source_path"] != f"source://{asset['source_id']}/{asset['relative_source_path']}":
            raise ValueError(f"asset {index} source provenance is not portable")
        if asset["state"] not in ASSET_STATES:
            raise ValueError(f"asset {index} has invalid state")
        if not isinstance(asset["size_bytes"], int) or asset["size_bytes"] < 0:
            raise ValueError(f"asset {index} has invalid size")
        targets.append(asset["target_path"])
    if targets != sorted(targets) or len(targets) != len(set(targets)):
        raise ValueError("asset targets must be unique and sorted")
    return manifest


def _is_reparse(path: Path) -> bool:
    if path.is_symlink():
        return True
    try:
        attributes = os.lstat(path).st_file_attributes
    except (AttributeError, FileNotFoundError, OSError):
        return False
    return bool(attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)
