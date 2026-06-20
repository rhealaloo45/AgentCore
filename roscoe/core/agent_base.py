"""Abstract base every agent inherits from."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class AgentBase(ABC):
    """Base class defining the agent contract + lifecycle hooks.

    The default agent (a tool-calling ReAct graph) is built inside ``AgentRunner``.
    Custom agents subclass this and implement :meth:`build_graph` to return a
    compiled LangGraph graph. Lifecycle hooks let middleware and subclasses observe
    the run without overriding the core loop.
    """

    @abstractmethod
    def build_graph(self) -> Any:
        """Build and return a compiled LangGraph graph for this agent."""
        raise NotImplementedError

    # --- lifecycle hooks (override as needed; no-ops by default) ---

    async def on_start(self, user_input: str, run_id: str) -> None:
        """Called before the graph runs."""

    async def on_end(self, result: Any) -> None:
        """Called after the graph produces a result."""

    async def on_error(self, error: Exception, run_id: str) -> None:
        """Called if the run raises."""
