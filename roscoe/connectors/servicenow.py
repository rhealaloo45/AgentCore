"""ServiceNow connector — pre-built tools over the Table API.

Auth: Basic with an instance username + password.

```yaml
connectors:
  servicenow:
    instance_url: ${SERVICENOW_URL}   # https://your-instance.service-now.com
    username: ${SERVICENOW_USER}
    password: ${SERVICENOW_PASSWORD}
```
"""

from __future__ import annotations

import base64
from typing import Any

from langchain_core.tools import StructuredTool

from roscoe.connectors.base_connector import BaseConnector

_TABLE = "/api/now/table"


class ServiceNowConnector(BaseConnector):
    """Tools: create_ticket, update_ticket, get_ticket_status, search_kb."""

    def _base_url(self) -> str:
        url = self.config.get("instance_url")
        if not url:
            raise ValueError(
                "servicenow connector config missing required key 'instance_url'."
            )
        return url.rstrip("/")

    def _auth_headers(self) -> dict[str, str]:
        for key in ("username", "password"):
            if not self.config.get(key):
                raise ValueError(
                    f"servicenow connector config missing required key '{key}'."
                )
        raw = f"{self.config['username']}:{self.config['password']}".encode()
        return {
            "Authorization": f"Basic {base64.b64encode(raw).decode()}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    @property
    def tools(self) -> list[StructuredTool]:
        def create_ticket(
            short_description: str, description: str = "", urgency: str = "3"
        ) -> Any:
            """Create a ServiceNow incident and return its number and sys_id."""
            return self._request(
                "POST",
                f"{_TABLE}/incident",
                json={
                    "short_description": short_description,
                    "description": description,
                    "urgency": urgency,
                },
            )

        def update_ticket(sys_id: str, fields: dict) -> Any:
            """Update fields on a ServiceNow incident by sys_id."""
            return self._request("PATCH", f"{_TABLE}/incident/{sys_id}", json=fields)

        def get_ticket_status(number: str) -> Any:
            """Look up an incident by its number (e.g. INC0010001)."""
            return self._request(
                "GET",
                f"{_TABLE}/incident",
                params={"sysparm_query": f"number={number}", "sysparm_limit": 1},
            )

        def search_kb(query: str, limit: int = 5) -> Any:
            """Search the ServiceNow knowledge base."""
            return self._request(
                "GET",
                f"{_TABLE}/kb_knowledge",
                params={"sysparm_query": f"short_descriptionLIKE{query}", "sysparm_limit": limit},
            )

        return [
            StructuredTool.from_function(create_ticket, description=create_ticket.__doc__),
            StructuredTool.from_function(update_ticket, description=update_ticket.__doc__),
            StructuredTool.from_function(
                get_ticket_status, description=get_ticket_status.__doc__
            ),
            StructuredTool.from_function(search_kb, description=search_kb.__doc__),
        ]
