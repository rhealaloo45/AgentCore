"""Threshold alerting over aggregated metrics.

Rules are evaluated against a :class:`~roscoe.monitoring.metrics.Metrics` snapshot —
pure, so the fire/don't-fire boundary is unit-testable. When a rule breaches, the
configured notifier is pinged. Thresholds come from the ``monitoring.alerts`` config.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from roscoe.monitoring.metrics import Metrics
from roscoe.monitoring.notifier import Notifier, NullNotifier


@dataclass
class Alert:
    """A single breached threshold."""

    rule: str
    value: float
    threshold: float

    @property
    def message(self) -> str:
        return f"{self.rule}: {self.value} exceeded threshold {self.threshold}"


def evaluate_alerts(metrics: Metrics, alerts_cfg: dict[str, Any] | None) -> list[Alert]:
    """Return the alerts that fire for ``metrics`` under ``alerts_cfg``.

    Recognised thresholds: ``daily_cost_usd``, ``error_rate_pct``, ``latency_p95_ms``.
    A threshold that's absent (or ``None``) is simply not checked. Comparison is strict
    ``>`` so a value exactly at the threshold does **not** fire.
    """
    cfg = alerts_cfg or {}
    fired: list[Alert] = []

    cost_t = cfg.get("daily_cost_usd")
    if cost_t is not None and metrics.max_daily_cost_usd > cost_t:
        fired.append(Alert("daily_cost_usd", metrics.max_daily_cost_usd, float(cost_t)))

    err_t = cfg.get("error_rate_pct")
    if err_t is not None and metrics.error_rate_pct > err_t:
        fired.append(Alert("error_rate_pct", metrics.error_rate_pct, float(err_t)))

    lat_t = cfg.get("latency_p95_ms")
    if lat_t is not None and metrics.max_p95_latency_ms > lat_t:
        fired.append(Alert("latency_p95_ms", metrics.max_p95_latency_ms, float(lat_t)))

    return fired


def check_and_notify(
    metrics: Metrics,
    alerts_cfg: dict[str, Any] | None,
    notifier: Notifier | None = None,
) -> list[Alert]:
    """Evaluate alerts and send each via ``notifier`` (no-op notifier if omitted)."""
    fired = evaluate_alerts(metrics, alerts_cfg)
    sink = notifier or NullNotifier()
    for alert in fired:
        sink.send(subject=f"roscoe alert: {alert.rule}", body=alert.message)
    return fired
