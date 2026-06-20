"""BaseConnector — shared interface + auth for pre-built tool collections.

A connector wraps an enterprise system's API behind ``@tool``-ready functions.
``connector.tools`` returns LangChain ``StructuredTool`` objects to hand straight to
``AgentRunner``. Auth is configured from the YAML ``connectors:`` block. An httpx
``transport`` can be injected for tests (so tools can be exercised without a live API).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import httpx
from langchain_core.tools import StructuredTool


class BaseConnector(ABC):
    """Base class all connectors implement."""

    #: Default per-request timeout (seconds).
    timeout: float = 30.0

    def __init__(self, config: dict[str, Any], *, transport: Any | None = None) -> None:
        self.config = config
        self._client = self._build_client(transport)

    def _build_client(self, transport: Any | None) -> httpx.Client:
        return httpx.Client(
            base_url=self._base_url(),
            headers=self._auth_headers(),
            timeout=self.timeout,
            transport=transport,
        )

    @abstractmethod
    def _base_url(self) -> str:
        """Return the API base URL."""

    @abstractmethod
    def _auth_headers(self) -> dict[str, str]:
        """Return auth headers applied to every request."""

    @property
    @abstractmethod
    def tools(self) -> list[StructuredTool]:
        """Return the connector's tools."""

    # --- helpers for subclasses ---

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        resp = self._client.request(method, path, **kwargs)
        resp.raise_for_status()
        if resp.content and "application/json" in resp.headers.get("content-type", ""):
            return resp.json()
        return {"status_code": resp.status_code, "text": resp.text}

    def close(self) -> None:
        self._client.close()
