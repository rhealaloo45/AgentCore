"""Google Workspace agent tools.

Gmail, Calendar, Tasks, and Drive via roscoe's ``GoogleWorkspaceConnector``.
The connector provides all seven tools (send_email, read_emails, list_events,
create_event, list_tasks, create_task, search_drive). Outgoing actions
(send_email, create_event, create_task) should be behind the approval gate.
"""

from __future__ import annotations

from typing import Any


def build_tools(google: Any) -> list:
    """Return the Google Workspace tools for the agent."""
    return list(google.tools)
