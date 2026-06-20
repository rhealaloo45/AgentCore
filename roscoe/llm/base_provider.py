"""BaseProvider — the interface custom providers implement.

A provider knows two things: how to build a LangChain chat model from a config
block, and what that model can do (``capabilities()``). After a user registers a
``BaseProvider`` via ``ProviderFactory.register()``, their model is indistinguishable
from the built-in five — same YAML, same middleware, same evals.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from langchain_core.language_models import BaseChatModel


class BaseProvider(ABC):
    """Contract for a provider that turns a config block into a chat model."""

    @abstractmethod
    def get_llm(self, config: dict[str, Any]) -> BaseChatModel:
        """Build a ``BaseChatModel`` from the ``model:`` block of agent_config.yaml."""
        raise NotImplementedError

    @abstractmethod
    def capabilities(self) -> dict[str, bool]:
        """Declare what this provider supports.

        Returns a dict with at least ``tool_calling``, ``streaming``,
        ``cost_tracking``, and ``rate_limiting`` booleans. The SDK reads these to
        catch problems early (e.g. tools requested but tool_calling is False).
        """
        raise NotImplementedError
