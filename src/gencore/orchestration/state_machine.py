"""Explicit S0-S5 stage transitions for progressive geometry design."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

from .contracts import Stage


class StageMachine:
    def __init__(self, transitions: Mapping[Stage, Mapping[str, Stage]]) -> None:
        self._transitions = {
            Stage(source): {
                str(event): Stage(target) for event, target in targets.items()
            }
            for source, targets in transitions.items()
        }
        if set(self._transitions) != set(Stage):
            raise ValueError("stage machine must declare every stage")

    @classmethod
    def default(cls, path: str | Path | None = None) -> "StageMachine":
        config_path = (
            Path(path)
            if path is not None
            else Path(__file__).resolve().parents[3]
            / "config"
            / "orchestration"
            / "stage_machine.json"
        )
        config = json.loads(config_path.read_text(encoding="utf-8"))
        if config.get("version") != 1:
            raise ValueError("stage machine config requires version 1")
        return cls(config["transitions"])

    def transition(self, current: Stage, event: str) -> Stage:
        stage = Stage(current)
        try:
            return self._transitions[stage][event]
        except KeyError as exc:
            raise ValueError(
                f"undefined stage transition: {stage.value} + {event}"
            ) from exc


__all__ = ["StageMachine"]
