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

import time
from typing import Any

from langchain_core.tools import StructuredTool

from roscoe.connectors.base_connector import BaseConnector

_GRAPH = "https://graph.microsoft.com/v1.0"


class OutlookConnector(BaseConnector):
    """Tools: send_email, read_emails, create_calendar_event, get_availability."""

    def __init__(self, config: dict[str, Any], *, transport: Any | None = None) -> None:
        self._token: str | None = None
        self._token_expiry: float = 0.0
        for key in ("client_id", "client_secret", "tenant_id", "mailbox"):
            if not config.get(key):
                raise ValueError(f"outlook connector config missing required key '{key}'.")
        super().__init__(config, transport=transport)

    def _base_url(self) -> str:
        return _GRAPH

    def _auth_headers(self) -> dict[str, str]:
        # Token is acquired lazily per request (see _request); nothing at build time.
        return {"Accept": "application/json", "Content-Type": "application/json"}

    def _ensure_token(self) -> str:
        if self._token and time.monotonic() < self._token_expiry:
            return self._token
        tenant = self.config["tenant_id"]
        resp = self._client.post(
            f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
            data={
                "grant_type": "client_credentials",
                "client_id": self.config["client_id"],
                "client_secret": self.config["client_secret"],
                "scope": "https://graph.microsoft.com/.default",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        self._token = data["access_token"]
        # refresh 60s early
        self._token_expiry = time.monotonic() + int(data.get("expires_in", 3600)) - 60
        return self._token

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self._ensure_token()}"
        return super()._request(method, path, headers=headers, **kwargs)

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
