"""Closed vocabularies for the multimodal engineering design state."""

from enum import Enum


class View(str, Enum):
    INTENT_REQUIREMENT = "intent_requirement"
    PRODUCT_FUNCTION = "product_function"
    PARAMETER_RULE = "parameter_rule"
    GEOMETRY_SPATIAL = "geometry_spatial"
    PROCESS_TOOL = "process_tool"
    RESULT_EVIDENCE = "result_evidence"


class ValueState(str, Enum):
    UNKNOWN = "unknown"
    OBSERVED = "observed"
    CANDIDATE = "candidate"
    INFERRED = "inferred"
    PROPOSED = "proposed"
    DERIVED = "derived"
    VERIFIED = "verified"
    CONFLICTED = "conflicted"
    SUPERSEDED = "superseded"
    REJECTED = "rejected"
