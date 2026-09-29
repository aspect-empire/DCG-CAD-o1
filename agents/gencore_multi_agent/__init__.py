"""Optional model-agent adapter for the portable GenCore runtime."""

from .builder import MultiAgentConfig, build_multi_agent
from .deepagent_adapter import DeepAgentRuntime

__all__ = [
    "DeepAgentRuntime",
    "MultiAgentConfig",
    "build_multi_agent",
]
