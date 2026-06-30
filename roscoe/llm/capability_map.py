"""Per-provider capability flags.

The SDK consults these to fail fast (e.g. an agent needs tool calling but the
provider can't do it) and to decide whether cost tracking / rate limiting apply.
Custom providers supply their own via ``BaseProvider.capabilities()``.
"""

from __future__ import annotations

CAPABILITIES: dict[str, dict[str, bool]] = {
    "azure_openai": {
        "tool_calling": True,
        "streaming": True,
        "cost_tracking": True,
        "rate_limiting": True,
    },
    "openai": {
        "tool_calling": True,
        "streaming": True,
        "cost_tracking": True,
        "rate_limiting": True,
    },
    "gemini": {
        "tool_calling": True,
        "streaming": True,
        "cost_tracking": True,
        "rate_limiting": True,
    },
    "anthropic": {
        "tool_calling": True,
        "streaming": True,
        "cost_tracking": True,
        "rate_limiting": True,
    },
    "ollama": {
        "tool_calling": True,  # model-dependent
        "streaming": True,
        "cost_tracking": False,  # local, always $0.00
        "rate_limiting": False,  # local, no external limits
    },
    "nvidia": {
        "tool_calling": True,  # model-dependent; most NIM models support it
        "streaming": True,
        "cost_tracking": True,
        "rate_limiting": True,
    },
}

_DEFAULT = {
    "tool_calling": False,
    "streaming": False,
    "cost_tracking": False,
    "rate_limiting": False,
}


def get_capabilities(provider: str) -> dict[str, bool]:
    """Return the capability flags for a provider (defaults to all-False)."""
    return dict(CAPABILITIES.get(provider, _DEFAULT))
