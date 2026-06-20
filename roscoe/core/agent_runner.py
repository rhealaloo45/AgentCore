"""AgentRunner — the main entry point.

``AgentRunner.from_config()`` reads a YAML config, builds a provider LLM and a
tool-calling ReAct graph, and exposes the run API. The core is **async-first**:
``arun()`` does the real work; ``run()`` is a thin ``asyncio.run`` wrapper for sync
callers.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Callable, Sequence
from uuid import uuid4

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.prebuilt import create_react_agent

from roscoe.config.loader import load_config
from roscoe.core.agent_result import AgentResult
from roscoe.llm.provider_factory import ProviderFactory


class AgentRunner:
    """Builds and runs a configured agent."""

    def __init__(
        self,
        *,
        config: dict[str, Any],
        graph: Any,
        agent_name: str,
        provider: str,
        model: str,
    ) -> None:
        self.config = config
        self._graph = graph
        self.agent_name = agent_name
        self.provider = provider
        self.model = model

    # --- construction ---

    @classmethod
    def from_config(
        cls,
        config_path: str | Path,
        tools: Sequence[Callable[..., Any]] | None = None,
    ) -> "AgentRunner":
        """Build an ``AgentRunner`` from a YAML config file.

        Args:
            config_path: Path to agent_config.yaml.
            tools: Tools (``@tool``-decorated functions) the agent may call.
        """
        config = load_config(config_path)
        model_cfg = config.get("model")
        if not model_cfg:
            raise ValueError("Config is missing the required 'model' block.")

        llm = ProviderFactory.get_llm(model_cfg)
        tool_list = list(tools or [])

        system_prompt = _load_system_prompt(config)
        kwargs: dict[str, Any] = {}
        if system_prompt:
            kwargs["state_modifier"] = system_prompt

        graph = create_react_agent(llm, tool_list, **kwargs)

        return cls(
            config=config,
            graph=graph,
            agent_name=config.get("agent_name", "roscoe-agent"),
            provider=model_cfg.get("provider", ""),
            model=model_cfg.get("deployment") or model_cfg.get("model", ""),
        )

    # --- execution ---

    async def arun(self, user_input: str, *, user_id: str | None = None) -> AgentResult:
        """Run the agent asynchronously and return an ``AgentResult``."""
        run_id = str(uuid4())
        try:
            state = await self._graph.ainvoke(
                {"messages": [HumanMessage(content=user_input)]}
            )
            messages = state.get("messages", [])
            return AgentResult(
                output=_final_text(messages),
                run_id=run_id,
                total_tokens=_count_tokens(messages),
                status="success",
            )
        except Exception as exc:  # noqa: BLE001 — surface any failure as a result
            return AgentResult(
                output="",
                run_id=run_id,
                error=f"{type(exc).__name__}: {exc}",
                status="error",
            )

    def run(self, user_input: str, *, user_id: str | None = None) -> AgentResult:
        """Synchronous wrapper around :meth:`arun`."""
        return asyncio.run(self.arun(user_input, user_id=user_id))


# --- helpers ---


def _load_system_prompt(config: dict[str, Any]) -> str | None:
    """Resolve a system prompt from an inline string or a file path."""
    if config.get("system_prompt"):
        return str(config["system_prompt"])
    prompt_file = config.get("system_prompt_file")
    if prompt_file:
        return Path(prompt_file).read_text()
    return None


def _final_text(messages: list[Any]) -> str:
    """Return the content of the last AI message."""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            content = msg.content
            return content if isinstance(content, str) else str(content)
    return ""


def _count_tokens(messages: list[Any]) -> int:
    """Sum total tokens across all messages that report usage metadata."""
    total = 0
    for msg in messages:
        usage = getattr(msg, "usage_metadata", None)
        if usage:
            total += usage.get("total_tokens", 0)
    return total
