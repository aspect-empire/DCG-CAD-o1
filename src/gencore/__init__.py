"""GenCore deterministic geometry tooling."""

__version__ = "0.1.0"
"""Deterministic geometry-generation tooling core."""

from .event_store import EventConflictError, JsonlEventStore
from .events import EngineeringEvent, EventSource
from .graph import EngineeringGraph
from .reasoner import GraphReasoner
from .skill_governance import SkillGovernance
from .design_state import DesignStateStore, GraphProposal, ProposalValidator, ValueState

__all__ = ["EngineeringEvent", "EventSource", "EventConflictError", "JsonlEventStore",
           "EngineeringGraph", "GraphReasoner", "SkillGovernance", "DesignStateStore",
           "GraphProposal", "ProposalValidator", "ValueState"]
