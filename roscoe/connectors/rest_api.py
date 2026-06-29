"""Generic REST connector — configurable GET/POST/PUT/DELETE tools.

Covers the common "just call our internal API" case. Auth is one of: ``api_key``
(custom header), ``bearer`` token, or ``basic`` (username/password).

```yaml
connectors:
  rest:
    base_url: ${SERVICE_URL}
    auth: bearer            # api_key | bearer | basic | none
    token: ${SERVICE_TOKEN}
```
"""

from __future__ import annotations

import base64
from typing import Any

from langchain_core.tools import StructuredTool

from roscoe.connectors.base_connector import BaseConnector


class RESTConnector(BaseConnector):
    """A configurable REST API connector."""

    def _base_url(self) -> str:
        url = self.config.get("base_url")
        if not url:
            raise ValueError("rest connector config missing required key 'base_url'.")
        return url

    def _auth_headers(self) -> dict[str, str]:
        auth = self.config.get("auth", "none")
        if auth == "none":
            return {}
        if auth == "bearer":
            return {"Authorization": f"Bearer {self.config['token']}"}
        if auth == "api_key":
            header = self.config.get("header", "X-API-Key")
            return {header: self.config["api_key"]}
        if auth == "basic":
            raw = f"{self.config['username']}:{self.config['password']}".encode()
            return {"Authorization": f"Basic {base64.b64encode(raw).decode()}"}
        raise ValueError(f"rest connector: unknown auth mode '{auth}'.")

    @property
    def tools(self) -> list[StructuredTool]:
        def rest_get(path: str, params: dict | None = None) -> Any:
            """Send a GET request to the configured API and return the JSON response."""
            return self._request("GET", path, params=params)

        def rest_post(path: str, body: dict | None = None) -> Any:
            """Send a POST request with a JSON body and return the JSON response."""
            return self._request("POST", path, json=body)

        def rest_put(path: str, body: dict | None = None) -> Any:
            """Send a PUT request with a JSON body and return the JSON response."""
            return self._request("PUT", path, json=body)

        def rest_delete(path: str) -> Any:
            """Send a DELETE request and return the JSON/status response."""
            return self._request("DELETE", path)

        return [
            StructuredTool.from_function(rest_get, description=rest_get.__doc__),
            StructuredTool.from_function(rest_post, description=rest_post.__doc__),
            StructuredTool.from_function(rest_put, description=rest_put.__doc__),
            StructuredTool.from_function(rest_delete, description=rest_delete.__doc__),
        ]
