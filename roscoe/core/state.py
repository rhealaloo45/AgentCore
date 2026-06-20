"""Base agent state schema for LangGraph graphs."""

from __future__ import annotations

from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """Minimal LangGraph state: an accumulating list of messages.

    The ``add_messages`` reducer appends new messages instead of overwriting,
    which is what the tool-calling loop needs. Subclasses can add fields (retrieved
    docs, scratchpad, etc.) while keeping ``messages``.
    """

    messages: Annotated[list[BaseMessage], add_messages]
