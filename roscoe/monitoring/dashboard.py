"""Terminal dashboard rendering — turns Metrics into a plain-text report.

Kept separate from the CLI (Phase 10) so it has no click/IO dependency and is testable:
the ``roscoe monitor`` command will simply ``print(render(aggregate(load_audit())))``.
"""

from __future__ import annotations

from roscoe.monitoring.metrics import Metrics


def render(metrics: Metrics) -> str:
    """Render a Metrics snapshot as a human-readable text block."""
    lines: list[str] = []
    lines.append("=== roscoe monitor ===")
    lines.append(f"runs: {metrics.total_runs}   error rate: {metrics.error_rate_pct}%   "
                 f"total cost: ${metrics.total_cost_usd}")

    if metrics.runs_by_status:
        status = "  ".join(f"{k}={v}" for k, v in sorted(metrics.runs_by_status.items()))
        lines.append(f"status: {status}")

    if metrics.cost_by_agent:
        lines.append("\ncost by agent:")
        for agent, cost in sorted(metrics.cost_by_agent.items(), key=lambda x: -x[1]):
            lines.append(f"  {agent:<24} ${cost}")

    if metrics.latency_ms_by_agent:
        lines.append("\nlatency (ms) by agent:")
        for agent, lat in sorted(metrics.latency_ms_by_agent.items()):
            lines.append(
                f"  {agent:<24} p50={lat['p50']}  p95={lat['p95']}  "
                f"p99={lat['p99']}  n={lat['count']}"
            )

    if metrics.errors_by_type:
        lines.append("\nerrors by type:")
        for etype, count in sorted(metrics.errors_by_type.items(), key=lambda x: -x[1]):
            lines.append(f"  {etype:<24} {count}")

    return "\n".join(lines)
