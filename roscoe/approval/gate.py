"""Human-approval gate and pending-run store (langgraph-free HITL).

roscoe runs its own ReAct loop, so human-in-the-loop is simple: when the model asks to
call a tool whose name is listed in ``require_approval_for``, the loop **stops** before
executing it and returns a ``paused`` result describing the pending tool call(s). A
human then approves / rejects / modifies out of band, and ``AgentRunner.resume()``
continues the run.

No checkpointer is needed: the paused run's message history is held in a
``PendingStore`` keyed by ``run_id``. The default store is in-process (good for a single
worker / dev). Swap in a durable store (sqlite, redis) for multi-process deployments.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class ApprovalGate:
    """Decides whether a tool call needs human approval before it runs."""

    def __init__(self, require_approval_for: list[str] | None = None) -> None:
        self._gated: set[str] = set(require_approval_for or [])

    def needs_approval(self, tool_name: str) -> bool:
        return tool_name in self._gated

    @property
    def is_active(self) -> bool:
        return bool(self._gated)


@dataclass
class PendingRun:
    """A run suspended awaiting human approval.

    Holds everything needed to resume: the conversation so far (the last message is the
    AIMessage carrying the gated ``tool_calls``), plus the run's identity so memory and
    audit can be updated on resume.
    """

    run_id: str
    messages: list[Any]
    tool_calls: list[dict[str, Any]]
    user_id: str | None = None
    session_id: str | None = None
    human_message: Any | None = None


class PendingStore:
    """In-process store of paused runs, keyed by ``run_id``.

    Intentionally tiny. For durability across process restarts or multiple workers,
    subclass and persist (sqlite/redis) — ``save`` / ``pop`` / ``get`` are the contract.
    """

    def __init__(self) -> None:
        self._runs: dict[str, PendingRun] = {}

    def save(self, run: PendingRun) -> None:
        self._runs[run.run_id] = run

    def get(self, run_id: str) -> PendingRun | None:
        return self._runs.get(run_id)

    def pop(self, run_id: str) -> PendingRun:
        if run_id not in self._runs:
            raise KeyError(
                f"No paused run with id '{run_id}'. It may have already been resumed, "
                f"or this process didn't create it (the default store is in-memory)."
            )
        return self._runs.pop(run_id)
