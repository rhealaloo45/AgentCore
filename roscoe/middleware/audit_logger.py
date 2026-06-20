"""Audit logger — non-blocking structured audit trail.

Records are pushed onto a ``queue.Queue`` and drained by a daemon worker thread, so
``AgentRunner`` returns without waiting on disk/DB. An ``atexit`` flush drains the
queue on process exit, so short-lived CLI/script runs never lose their last record.

This deliberately avoids ``asyncio.create_task`` (needs a running loop; fire-and-forget
tasks die when the loop closes), so it works identically in sync, async, CLI, and
server contexts.

Sink for Phase 3 is ``local`` (one JSON line per run in ``./logs/audit.jsonl``).
``azure_table`` / ``postgres`` sinks come later.
"""

from __future__ import annotations

import atexit
import json
import queue
import threading
from pathlib import Path
from typing import Any

_SENTINEL = object()


class AuditLogger:
    """Background-thread, queue-backed audit writer (local JSONL sink)."""

    def __init__(self, log_dir: str | Path = "logs", filename: str = "audit.jsonl") -> None:
        self._dir = Path(log_dir)
        self._path = self._dir / filename
        self._queue: queue.Queue[Any] = queue.Queue()
        self._worker = threading.Thread(target=self._run, name="roscoe-audit", daemon=True)
        self._started = False
        self._lock = threading.Lock()

    def _ensure_started(self) -> None:
        with self._lock:
            if not self._started:
                self._dir.mkdir(parents=True, exist_ok=True)
                self._worker.start()
                atexit.register(self.flush)
                self._started = True

    def log(self, record: dict[str, Any]) -> None:
        """Enqueue a record (non-blocking)."""
        self._ensure_started()
        self._queue.put(record)

    def flush(self, timeout: float | None = 5.0) -> None:
        """Block until the queue is drained (called on exit; safe to call directly)."""
        if not self._started:
            return
        self._queue.join() if timeout is None else self._join_with_timeout(timeout)

    def _join_with_timeout(self, timeout: float) -> None:
        # queue.join has no timeout; poll unfinished tasks instead.
        import time

        deadline = time.monotonic() + timeout
        while self._queue.unfinished_tasks and time.monotonic() < deadline:
            time.sleep(0.01)

    def _run(self) -> None:
        while True:
            record = self._queue.get()
            try:
                if record is _SENTINEL:
                    return
                with self._path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(record, default=str) + "\n")
            except Exception:  # noqa: BLE001 — audit must never crash the worker
                pass
            finally:
                self._queue.task_done()


# Process-wide default logger (lazily started on first use).
_default = AuditLogger()


def get_audit_logger() -> AuditLogger:
    """Return the process-wide audit logger."""
    return _default
