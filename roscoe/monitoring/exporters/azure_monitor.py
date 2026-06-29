"""Azure Monitor exporter (optional).

Pushes metrics through OpenTelemetry to Azure Monitor / Application Insights via the
``azure-monitor-opentelemetry`` package — an **optional** dependency. Install with
``pip install "roscoe[azure]"``.

The exporter records each metric as an OpenTelemetry gauge observation. A meter can be
injected (``meter=...``) so the push path is testable without the SDK or a live
connection string.
"""

from __future__ import annotations

from typing import Any

from roscoe.monitoring.metrics import Metrics


class AzureMonitorExporter:
    """Sends aggregated metrics to Azure Monitor."""

    def __init__(self, connection_string: str | None = None, *, meter: Any | None = None) -> None:
        self._meter = meter if meter is not None else self._build_meter(connection_string)

    def _build_meter(self, connection_string: str | None) -> Any:
        if not connection_string:
            raise ValueError("AzureMonitorExporter requires a connection_string (or an injected meter).")
        try:
            from azure.monitor.opentelemetry import configure_azure_monitor  # type: ignore
            from opentelemetry import metrics as otel_metrics  # type: ignore
        except ImportError as exc:  # pragma: no cover - only without the extra
            raise ImportError(
                "The Azure Monitor exporter needs the optional dependency. Install it with "
                '`pip install "roscoe[azure]"`.'
            ) from exc

        configure_azure_monitor(connection_string=connection_string)
        return otel_metrics.get_meter("roscoe")

    def export(self, metrics: Metrics) -> None:
        """Record the headline gauges via the meter."""
        self._gauge("roscoe.runs_total", metrics.total_runs)
        self._gauge("roscoe.error_rate_pct", metrics.error_rate_pct)
        self._gauge("roscoe.cost_usd_total", metrics.total_cost_usd)
        for agent, cost in metrics.cost_by_agent.items():
            self._gauge("roscoe.cost_usd_by_agent", cost, attributes={"agent": agent})

    def _gauge(self, name: str, value: float, attributes: dict[str, Any] | None = None) -> None:
        # OpenTelemetry gauges are created once and observed; for a one-shot push we use
        # the meter's record helper (mockable). Real meters expose create_gauge().
        gauge = self._meter.create_gauge(name)
        gauge.set(value, attributes or {})
