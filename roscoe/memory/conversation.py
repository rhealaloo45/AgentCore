"""Conversation memory — in-session chat history.

Stores the running message history per ``session_id`` and trims it to a window so
token usage stays bounded. ``AgentRunner`` injects the history before each turn and
appends the new turn after, so a follow-up question can reference earlier answers.
"""

from __future__ import annotations

from langchain_core.messages import BaseMessage


class ConversationMemory:
    """Per-session message history with a sliding window."""

    def __init__(self, window_size: int = 10) -> None:
        if window_size <= 0:
            raise ValueError("window_size must be positive.")
        self.window_size = window_size
        self._store: dict[str, list[BaseMessage]] = {}

    def get(self, session_id: str) -> list[BaseMessage]:
        """Return the trimmed history for a session (most recent ``window_size``)."""
        return list(self._store.get(session_id, []))

    def add(self, session_id: str, *messages: BaseMessage) -> None:
        """Append messages to a session, trimming to the window."""
        history = self._store.setdefault(session_id, [])
        history.extend(messages)
        if len(history) > self.window_size:
            del history[: len(history) - self.window_size]

    def clear(self, session_id: str) -> None:
        self._store.pop(session_id, None)
