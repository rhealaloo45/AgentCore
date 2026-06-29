"""``roscoe monitor`` — terminal dashboard from local audit logs.

Reads the JSONL audit log, aggregates it (Phase 7), and prints the dashboard. Pure local
read — no exporter or network involved.
"""

from __future__ import annotations

import click

from roscoe.monitoring import aggregate, load_audit, render
from roscoe.monitoring.metrics import DEFAULT_AUDIT_PATH


@click.command("monitor")
@click.option(
    "--path",
    "audit_path",
    default=str(DEFAULT_AUDIT_PATH),
    show_default=True,
    help="Path to the JSONL audit log.",
)
def monitor_command(audit_path: str) -> None:
    """Show cost, latency, and error metrics from local audit logs."""
    records = load_audit(audit_path)
    if not records:
        click.echo(f"No audit records found at {audit_path}. Run an agent first.")
        return
    click.echo(render(aggregate(records)))
