"""AgentRunner — the main entry point, with middleware wired in.

``from_config()`` builds a provider LLM (with retry applied), a tool-calling ReAct
graph, and the per-run middleware stack. The core is **async-first**: ``arun()`` does
the work; ``run()`` is a thin ``asyncio.run`` wrapper.

Every run automatically gets: rate limiting (before the call), retry (around each LLM
call), cost tracking (after), and a non-blocking audit record — with zero extra code
from the developer.
"""

from __future__ import annotations

import asyncio
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence
from uuid import uuid4

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent

from roscoe.config.loader import load_config
from roscoe.core.agent_result import AgentResult
from roscoe.llm.provider_factory import ProviderFactory
from roscoe.memory.conversation import ConversationMemory
from roscoe.memory.persistent import PersistentMemory
from roscoe.middleware.audit_logger import get_audit_logger
from roscoe.middleware.cost_tracker import calculate_cost, sum_usage
from roscoe.middleware.rate_limiter import RateLimiter
from roscoe.middleware.retry import apply_retry


class AgentRunner:
    """Builds and runs a configured agent with the full middleware stack."""

    def __init__(
        self,
        *,
        config: dict[str, Any],
        graph: Any,
        agent_name: str,
        provider: str,
        model: str,
        middleware: dict[str, Any],
        rate_limiter: RateLimiter,
        conversation: ConversationMemory | None = None,
        persistent: PersistentMemory | None = None,
    ) -> None:
        self.config = config
        self._graph = graph
        self.agent_name = agent_name
        self.provider = provider
        self.model = model
        self._mw = middleware
        self._rate_limiter = rate_limiter
        self._conversation = conversation
        self._persistent = persistent
        self._audit = get_audit_logger()

    # --- construction ---

    @classmethod
    def from_config(
        cls,
        config_path: str | Path,
        tools: Sequence[Callable[..., Any]] | None = None,
    ) -> "AgentRunner":
        config = load_config(config_path)
        model_cfg = config.get("model")
        if not model_cfg:
            raise ValueError("Config is missing the required 'model' block.")

        provider = model_cfg.get("provider", "")
        middleware = config.get("middleware", {}) or {}
        tool_list = list(tools or [])

        # Fail-fast capability check.
        caps = ProviderFactory.capabilities(provider)
        if tool_list and not caps.get("tool_calling", False):
            warnings.warn(
                f"Provider '{provider}' declares tool_calling=False but {len(tool_list)} "
                f"tool(s) were supplied; tool calls may fail at runtime.",
                stacklevel=2,
            )

        llm = ProviderFactory.get_llm(model_cfg)
        # Bind tools BEFORE applying retry. `with_retry` on a tool-bound model keeps
        # the RunnableBinding outermost (so create_react_agent sees the tools and
        # skips re-binding); retrying the raw model first yields a RunnableRetry with
        # no `bind_tools`, which create_react_agent then fails to bind.
        model: Any = llm.bind_tools(tool_list) if tool_list else llm
        model = apply_retry(model, middleware.get("retry"), provider)

        system_prompt = _load_system_prompt(config)
        kwargs: dict[str, Any] = {}
        if system_prompt:
            kwargs["state_modifier"] = system_prompt
        graph = create_react_agent(model, tool_list, **kwargs)

        rate_limiter = RateLimiter()
        rate_limiter.configure(provider, middleware.get("rate_limiter"))

        conversation, persistent = _build_memory(config.get("memory", {}) or {})

        return cls(
            config=config,
            graph=graph,
            agent_name=config.get("agent_name", "roscoe-agent"),
            provider=provider,
            model=model_cfg.get("deployment") or model_cfg.get("model", ""),
            middleware=middleware,
            rate_limiter=rate_limiter,
            conversation=conversation,
            persistent=persistent,
        )

    # --- execution ---

    async def arun(
        self,
        user_input: str,
        *,
        user_id: str | None = None,
        session_id: str | None = None,
    ) -> AgentResult:
        run_id = str(uuid4())
        start = datetime.now(timezone.utc)

        await self._rate_limiter.acquire(self.provider)

        human = HumanMessage(content=user_input)
        input_messages = self._build_input(human, user_id, session_id)

        try:
            state = await self._graph.ainvoke({"messages": input_messages})
            messages = state.get("messages", [])
            inp, out, total = sum_usage(messages)
            output = _final_text(messages)
            result = AgentResult(
                output=output,
                run_id=run_id,
                total_tokens=total,
                cost_usd=self._cost(inp, out),
                status="success",
            )
            if self._conversation is not None and session_id is not None:
                self._conversation.add(session_id, human, AIMessage(content=output))
        except Exception as exc:  # noqa: BLE001 — surface any failure as a result
            result = AgentResult(
                output="",
                run_id=run_id,
                error=f"{type(exc).__name__}: {exc}",
                status="error",
            )

        self._write_audit(result, user_id, start)
        return result

    def run(
        self,
        user_input: str,
        *,
        user_id: str | None = None,
        session_id: str | None = None,
    ) -> AgentResult:
        return asyncio.run(
            self.arun(user_input, user_id=user_id, session_id=session_id)
        )

    def _build_input(
        self, human: HumanMessage, user_id: str | None, session_id: str | None
    ) -> list[Any]:
        """Assemble the input message list: facts + history + the new turn."""
        messages: list[Any] = []
        # Persistent facts -> a system note loaded into context.
        if self._persistent is not None and user_id is not None:
            facts = self._persistent.all(user_id)
            if facts:
                rendered = "; ".join(f"{k}={v}" for k, v in facts.items())
                messages.append(SystemMessage(content=f"Known facts: {rendered}"))
        # Conversation history for this session.
        if self._conversation is not None and session_id is not None:
            messages.extend(self._conversation.get(session_id))
        messages.append(human)
        return messages

    # --- middleware helpers ---

    def _cost(self, input_tokens: int, output_tokens: int) -> float | None:
        if self._mw.get("cost_tracking", {}).get("enabled", True) is False:
            return None
        return calculate_cost(self.provider, self.model, input_tokens, output_tokens)

    def _write_audit(
        self, result: AgentResult, user_id: str | None, start: datetime
    ) -> None:
        if self._mw.get("audit", {}).get("enabled", True) is False:
            return
        self._audit.log(
            {
                "run_id": result.run_id,
                "agent_name": self.agent_name,
                "user_id": user_id,
                "provider": self.provider,
                "model": self.model,
                "start_time": start.isoformat(),
                "end_time": datetime.now(timezone.utc).isoformat(),
                "total_tokens": result.total_tokens,
                "cost_usd": result.cost_usd,
                "nodes_traversed": result.nodes_traversed,
                "status": result.status,
                "error": result.error,
            }
        )


# --- helpers ---


def _build_memory(
    memory_cfg: dict[str, Any],
) -> tuple[ConversationMemory | None, PersistentMemory | None]:
    """Build conversation + persistent memory from the ``memory:`` config block."""
    conversation = None
    conv_cfg = memory_cfg.get("conversation", {}) or {}
    if conv_cfg.get("enabled"):
        conversation = ConversationMemory(window_size=conv_cfg.get("window_size", 10))

    persistent = None
    pers_cfg = memory_cfg.get("persistent", {}) or {}
    if pers_cfg.get("enabled"):
        persistent = PersistentMemory(
            backend=pers_cfg.get("backend", "sqlite"),
            connection=pers_cfg.get("connection", ":memory:"),
        )

    return conversation, persistent


def _load_system_prompt(config: dict[str, Any]) -> str | None:
    if config.get("system_prompt"):
        return str(config["system_prompt"])
    prompt_file = config.get("system_prompt_file")
    if prompt_file:
        return Path(prompt_file).read_text()
    return None


def _final_text(messages: list[Any]) -> str:
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            content = msg.content
            return content if isinstance(content, str) else str(content)
    return ""
