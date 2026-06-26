"""Base agent state schema.

roscoe runs its own ReAct loop (see ``roscoe.core.executor``) rather than a LangGraph
graph, so the message list is managed explicitly — no reducer needed. This TypedDict is
kept for typing the message channel that flows through the loop.
"""

from __future__ import annotations

from typing import TypedDict

from langchain_core.messages import BaseMessage


class AgentState(TypedDict):
    """Minimal agent state: the running list of messages for the tool-calling loop."""

    messages: list[BaseMessage]
