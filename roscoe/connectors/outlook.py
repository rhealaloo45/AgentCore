"""Outlook connector — pre-built tools over Microsoft Graph (app-only OAuth2).

Authenticates with the client-credentials flow (Azure AD app registration), caches
the bearer token, and acts on a configured mailbox.

```yaml
connectors:
  outlook:
    client_id: ${OUTLOOK_CLIENT_ID}
    client_secret: ${OUTLOOK_CLIENT_SECRET}
    tenant_id: ${OUTLOOK_TENANT_ID}
    mailbox: ${OUTLOOK_MAILBOX}        # UPN/object id the app acts on behalf of
```

Note: app-only Graph access requires the app registration to hold the relevant
application permissions (Mail.Send, Mail.Read, Calendars.ReadWrite) with admin consent.
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import StructuredTool

from roscoe.connectors._graph_base import GraphConnector


class OutlookConnector(GraphConnector):
    """Tools: send_email, read_emails, create_calendar_event, get_availability."""

    extra_required = ("mailbox",)

    @property
    def tools(self) -> list[StructuredTool]:
        mbx = self.config["mailbox"]

        def send_email(to: str, subject: str, body: str) -> Any:
            """Send an email from the configured mailbox."""
            payload = {
                "message": {
                    "subject": subject,
                    "body": {"contentType": "Text", "content": body},
                    "toRecipients": [{"emailAddress": {"address": to}}],
                }
            }
            return self._request("POST", f"/users/{mbx}/sendMail", json=payload)

        def read_emails(top: int = 10) -> Any:
            """Read the most recent emails in the mailbox inbox."""
            return self._request(
                "GET", f"/users/{mbx}/messages", params={"$top": top}
            )

        def create_calendar_event(
            subject: str, start: str, end: str, attendees: list[str] | None = None
        ) -> Any:
            """Create a calendar event. start/end are ISO 8601 datetimes (UTC)."""
            payload: dict[str, Any] = {
                "subject": subject,
                "start": {"dateTime": start, "timeZone": "UTC"},
                "end": {"dateTime": end, "timeZone": "UTC"},
            }
            if attendees:
                payload["attendees"] = [
                    {"emailAddress": {"address": a}, "type": "required"} for a in attendees
                ]
            return self._request("POST", f"/users/{mbx}/events", json=payload)

        def get_availability(emails: list[str], start: str, end: str) -> Any:
            """Get free/busy availability for the given mailboxes over a time window."""
            payload = {
                "schedules": emails,
                "startTime": {"dateTime": start, "timeZone": "UTC"},
                "endTime": {"dateTime": end, "timeZone": "UTC"},
                "availabilityViewInterval": 60,
            }
            return self._request(
                "POST", f"/users/{mbx}/calendar/getSchedule", json=payload
            )

        return [
            StructuredTool.from_function(send_email, description=send_email.__doc__),
            StructuredTool.from_function(read_emails, description=read_emails.__doc__),
            StructuredTool.from_function(
                create_calendar_event, description=create_calendar_event.__doc__
            ),
            StructuredTool.from_function(
                get_availability, description=get_availability.__doc__
            ),
        ]
