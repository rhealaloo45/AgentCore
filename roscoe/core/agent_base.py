"""Abstract base every agent inherits from."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class AgentBase(ABC):
    """Base class defining the agent contract + lifecycle hooks.

    The default agent (a tool-calling ReAct loop) is built inside ``AgentRunner`` using
    ``roscoe.core.executor.ReactExecutor`` — no LangGraph. Custom agents subclass this
    and implement :meth:`build_executor` to return their own executor. Lifecycle hooks
    let middleware and subclasses observe the run without overriding the core loop.
    """

    @abstractmethod
    def build_executor(self) -> Any:
        """Build and return the executor that drives this agent's loop."""
        raise NotImplementedError

    # --- lifecycle hooks (override as needed; no-ops by default) ---

    async def on_start(self, user_input: str, run_id: str) -> None:
        """Called before the run starts."""

    async def on_end(self, result: Any) -> None:
        """Called after the run produces a result."""

    async def on_error(self, error: Exception, run_id: str) -> None:
        """Called if the run raises."""
