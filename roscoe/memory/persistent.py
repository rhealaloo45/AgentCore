"""Persistent memory — cross-session key/value facts per user.

Stores facts keyed by ``user_id`` so a fact learned in one run is available in the
next. SQLite is the dev/default backend (a real file or ``:memory:``); Postgres and
Azure Table Storage are recognised but not yet implemented.
"""

from __future__ import annotations

import sqlite3
import threading
from typing import Any


class PersistentMemory:
    """Key/value fact store scoped by user_id."""

    def __init__(self, backend: str = "sqlite", connection: str = ":memory:") -> None:
        if backend != "sqlite":
            raise NotImplementedError(
                f"Persistent memory backend '{backend}' is not implemented yet "
                f"(sqlite is available; postgres/azure_table are planned)."
            )
        self.backend = backend
        self._lock = threading.Lock()
        # check_same_thread=False so the audit/other threads can share if needed.
        self._conn = sqlite3.connect(connection, check_same_thread=False)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS facts ("
            "user_id TEXT NOT NULL, key TEXT NOT NULL, value TEXT, "
            "PRIMARY KEY (user_id, key))"
        )
        self._conn.commit()

    def set(self, user_id: str, key: str, value: Any) -> None:
        """Store (or overwrite) a fact for a user."""
        with self._lock:
            self._conn.execute(
                "INSERT INTO facts (user_id, key, value) VALUES (?, ?, ?) "
                "ON CONFLICT(user_id, key) DO UPDATE SET value = excluded.value",
                (user_id, key, str(value)),
            )
            self._conn.commit()

    def get(self, user_id: str, key: str) -> str | None:
        cur = self._conn.execute(
            "SELECT value FROM facts WHERE user_id = ? AND key = ?", (user_id, key)
        )
        row = cur.fetchone()
        return row[0] if row else None

    def all(self, user_id: str) -> dict[str, str]:
        """Return all facts for a user as a dict."""
        cur = self._conn.execute(
            "SELECT key, value FROM facts WHERE user_id = ?", (user_id,)
        )
        return {k: v for k, v in cur.fetchall()}

    def close(self) -> None:
        self._conn.close()
