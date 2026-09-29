"""Public interface for the versioned multimodal design-state kernel."""

from .dependencies import affected_closure
from .alignment import AlignmentEngine, AlignmentResult
from .geometry import GeometryLevel, GeometryReference, ReferenceResolver, Resolution
from .inference import build_invalidation_proposal
from .ontology import ValueState, View
from .proposals import GraphOperation, GraphProposal
from .records import DesignNode, EvidenceRef
from .versions import DesignStateStore, GraphVersion, VersionEvent
from .validator import ProposalConflict, ProposalValidator, ValidationResult

__all__ = [
    "DesignNode",
    "AlignmentEngine",
    "AlignmentResult",
    "DesignStateStore",
    "EvidenceRef",
    "GeometryLevel",
    "GeometryReference",
    "GraphOperation",
    "GraphProposal",
    "GraphVersion",
    "ProposalConflict",
    "ProposalValidator",
    "ReferenceResolver",
    "Resolution",
    "ValueState",
    "ValidationResult",
    "VersionEvent",
    "View",
    "affected_closure",
    "build_invalidation_proposal",
]
