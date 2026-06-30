"""The ``AgentResult`` returned by every agent run."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentResult:
    """The outcome of a single ``AgentRunner.run()`` / ``arun()`` call.

    Attributes:
        output: The agent's final answer text.
        run_id: UUID for the run — the key tying it to the audit trail.
        total_tokens: Total tokens across all LLM calls in the run.
        cost_usd: Estimated cost in USD. ``None`` until the Phase 3 cost tracker
            populates it.
        error: Error message if the run failed, else ``None``.
        status: ``"success"`` | ``"error"`` | ``"paused"`` | ``"rate_limited"``.
            ``paused`` = awaiting human approval. ``rate_limited`` = retries
            exhausted due to provider rate limits; caller should retry later.
        pending_action: When ``status == "paused"``, the intercepted tool call
            awaiting approval; otherwise ``None``.
        tool_calls: Ordered names of tools the agent invoked during the run. Used by
            the Phase 8 tool-usage scorer.
        nodes_traversed: Ordered names of graph nodes visited during the run.
    """

    output: str
    run_id: str
    total_tokens: int = 0
    cost_usd: float | None = None
    error: str | None = None
    status: str = "success"
    pending_action: dict[str, Any] | None = None
    tool_calls: list[str] = field(default_factory=list)
    nodes_traversed: list[str] = field(default_factory=list)
