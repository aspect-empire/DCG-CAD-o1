"""Exactly five model-enabled specialist definitions."""

from __future__ import annotations

from typing import Any

from gencore.orchestration.roles import AgentRole

from .prompts import SPECIALIST_PROMPTS
from .tool_facade import ToolFacade


SPECIALISTS = (
    ("scene-constraint-agent", AgentRole.SCENE_CONSTRAINT),
    ("solution-parameter-agent", AgentRole.SOLUTION_PARAMETER),
    ("geometry-planning-agent", AgentRole.GEOMETRY_PLANNING),
    ("validation-agent", AgentRole.VALIDATION),
    ("repair-reflection-agent", AgentRole.REPAIR_REFLECTION),
)


def build_specialists(model: Any, facade: ToolFacade) -> list[dict[str, Any]]:
    return [
        {
            "name": name,
            "description": SPECIALIST_PROMPTS[name],
            "system_prompt": SPECIALIST_PROMPTS[name],
            "tools": facade.tools_for(role),
            "model": model,
        }
        for name, role in SPECIALISTS
    ]


__all__ = ["SPECIALISTS", "build_specialists"]
