"""LLM subpackage — provider factory + custom-provider interface."""

from roscoe.llm.base_provider import BaseProvider
from roscoe.llm.capability_map import get_capabilities
from roscoe.llm.provider_factory import ProviderFactory

__all__ = ["BaseProvider", "ProviderFactory", "get_capabilities"]
