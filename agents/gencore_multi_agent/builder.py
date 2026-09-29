"""Build the optional DeepAgent root without owning model credentials."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from gencore.orchestration import AgentOutcome

from .prompts import ROOT_PROMPT
from .specialists import build_specialists
from .tool_facade import ToolFacade


@dataclass(frozen=True)
class MultiAgentConfig:
    model: Any
    workspace_root: str | Path
    allow_external_cad: bool = False
    checkpointer: Any | None = None
    backend: Any | None = None

    def __post_init__(self) -> None:
        if self.model is None or (
            isinstance(self.model, str) and not self.model.strip()
        ):
            raise ValueError("model must be supplied by the caller")
        if not str(self.workspace_root).strip():
            raise ValueError("workspace_root must be supplied by the caller")
        object.__setattr__(
            self, "workspace_root", Path(self.workspace_root).absolute()
        )


def build_multi_agent(
    config: MultiAgentConfig,
    *,
    builder: Any | None = None,
) -> Any:
    if builder is None:
        try:
            from deepagents import create_deep_agent
        except ImportError as exc:
            raise RuntimeError(
                "Deep Agents is optional; install GenCore with the 'agent' extra."
            ) from exc
        builder = create_deep_agent

    facade = ToolFacade(
        workspace_root=config.workspace_root,
        allow_external_cad=config.allow_external_cad,
    )
    kwargs: dict[str, Any] = {
        "name": "gencore-root-coordinator",
        "model": config.model,
        "tools": facade.root_tools(),
        "system_prompt": ROOT_PROMPT,
        "subagents": build_specialists(config.model, facade),
        "response_format": AgentOutcome,
    }
    if config.allow_external_cad:
        kwargs["interrupt_on"] = {
            name: True for name in facade.external_tool_names()
        }
    if config.checkpointer is not None:
        kwargs["checkpointer"] = config.checkpointer
    if config.backend is not None:
        kwargs["backend"] = config.backend
    return builder(**kwargs)


__all__ = ["MultiAgentConfig", "build_multi_agent"]
