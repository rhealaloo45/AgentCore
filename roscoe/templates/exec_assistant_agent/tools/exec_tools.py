"""Executive assistant agent tools.

Email and calendar over Microsoft 365 via roscoe's ``OutlookConnector`` (Graph OAuth2).
The connector's tools (send_email, read_emails, create_calendar_event, get_availability)
are exactly the domain surface, so ``build_tools`` returns them directly. Put outgoing
actions (send_email, create_calendar_event) behind the approval gate in the config.
"""

from __future__ import annotations

from typing import Any


def build_tools(outlook: Any) -> list:
    """Return the Outlook email/calendar tools for the assistant."""
    return list(outlook.tools)
