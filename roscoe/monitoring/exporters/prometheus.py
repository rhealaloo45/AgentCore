"""Prometheus Pushgateway exporter.

An SDK mostly runs as short-lived processes, so the default is a **push** to a
Pushgateway (a resident ``/metrics`` scrape endpoint only makes sense under the optional
``roscoe serve``, added with the CLI). This builds the Prometheus text exposition format
and POSTs it — no ``prometheus_client`` dependency. ``transport`` is injectable for tests.
"""

from __future__ import annotations

from typing import Any

import httpx

from roscoe.monitoring.metrics import Metrics


class PrometheusPushgatewayExporter:
    """Pushes aggregated metrics to a Prometheus Pushgateway."""

    def __init__(
        self,
        pushgateway_url: str,
        *,
        job: str = "roscoe",
        transport: Any | None = None,
    ) -> None:
        if not pushgateway_url:
            raise ValueError("PrometheusPushgatewayExporter requires a pushgateway_url.")
        self._url = pushgateway_url.rstrip("/")
        self._job = job
        self._client = httpx.Client(timeout=10.0, transport=transport)

    def export(self, metrics: Metrics) -> httpx.Response:
        """Push ``metrics`` to ``{pushgateway_url}/metrics/job/{job}``."""
        body = self.format_metrics(metrics)
        resp = self._client.post(
            f"{self._url}/metrics/job/{self._job}",
            content=body,
            headers={"Content-Type": "text/plain"},
        )
        resp.raise_for_status()
        return resp

    def format_metrics(self, metrics: Metrics) -> str:
        """Render metrics in the Prometheus text exposition format."""
        lines: list[str] = []
        lines.append("# TYPE roscoe_runs_total counter")
        lines.append(f"roscoe_runs_total {metrics.total_runs}")
        lines.append("# TYPE roscoe_error_rate_pct gauge")
        lines.append(f"roscoe_error_rate_pct {metrics.error_rate_pct}")
        lines.append("# TYPE roscoe_cost_usd_total gauge")
        lines.append(f"roscoe_cost_usd_total {metrics.total_cost_usd}")

        lines.append("# TYPE roscoe_cost_usd_by_agent gauge")
        for agent, cost in metrics.cost_by_agent.items():
            lines.append(f'roscoe_cost_usd_by_agent{{agent="{_esc(agent)}"}} {cost}')

        lines.append("# TYPE roscoe_latency_ms gauge")
        for agent, lat in metrics.latency_ms_by_agent.items():
            for quantile in ("p50", "p95", "p99"):
                lines.append(
                    f'roscoe_latency_ms{{agent="{_esc(agent)}",quantile="{quantile}"}} '
                    f'{lat[quantile]}'
                )
        return "\n".join(lines) + "\n"


def _esc(label: str) -> str:
    return label.replace("\\", "\\\\").replace('"', '\\"')
