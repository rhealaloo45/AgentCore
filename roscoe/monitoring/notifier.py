"""Notifiers — where alerts (and human-approval requests) are delivered.

Built here in Phase 7 because alerting needs it; the Phase 6 approval flow can reuse the
same ``Notifier`` to ping a human when a run pauses. Slack uses an incoming-webhook URL
via httpx, with an injectable ``transport`` so it's testable without a live webhook.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import httpx


class Notifier(ABC):
    """Sends a short message somewhere a human will see it."""

    @abstractmethod
    def send(self, subject: str, body: str) -> None: ...


class NullNotifier(Notifier):
    """Drops messages. Default when notifications are disabled."""

    def send(self, subject: str, body: str) -> None:  # noqa: D102
        return None


class ConsoleNotifier(Notifier):
    """Prints to stdout. Useful in dev and for the CLI."""

    def send(self, subject: str, body: str) -> None:  # noqa: D102
        print(f"[roscoe] {subject}\n{body}")


class SlackNotifier(Notifier):
    """Posts to a Slack incoming webhook."""

    def __init__(self, webhook_url: str, *, transport: Any | None = None) -> None:
        if not webhook_url:
            raise ValueError("SlackNotifier requires a webhook_url.")
        self._url = webhook_url
        self._client = httpx.Client(timeout=10.0, transport=transport)

    def send(self, subject: str, body: str) -> None:  # noqa: D102
        resp = self._client.post(self._url, json={"text": f"*{subject}*\n{body}"})
        resp.raise_for_status()


def build_notifier(
    name: str | None, config: dict[str, Any] | None = None, *, transport: Any | None = None
) -> Notifier:
    """Build a notifier by name from a monitoring/alerts config block.

    ``name`` ∈ ``slack`` | ``console`` | ``none`` (or ``None``). Slack reads
    ``config['slack_webhook_url']`` (typically a ``${ENV_VAR}``).
    """
    cfg = config or {}
    if name == "slack":
        return SlackNotifier(cfg.get("slack_webhook_url", ""), transport=transport)
    if name == "console":
        return ConsoleNotifier()
    return NullNotifier()
