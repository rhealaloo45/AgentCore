"""Notion connector — pre-built tools over the Notion REST API.

Auth: an internal integration token (bearer). The integration must be shared with
the pages/databases it should access.

```yaml
connectors:
  notion:
    token: ${NOTION_TOKEN}
    version: "2022-06-28"     # optional Notion-Version header
```
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import StructuredTool

from roscoe.connectors.base_connector import BaseConnector

_BASE = "https://api.notion.com/v1"


class NotionConnector(BaseConnector):
    """Tools: search, get_page, create_page, query_database, append_block."""

    def _base_url(self) -> str:
        return _BASE

    def _auth_headers(self) -> dict[str, str]:
        if not self.config.get("token"):
            raise ValueError("notion connector config missing required key 'token'.")
        return {
            "Authorization": f"Bearer {self.config['token']}",
            "Notion-Version": self.config.get("version", "2022-06-28"),
            "Content-Type": "application/json",
        }

    @property
    def tools(self) -> list[StructuredTool]:
        def search(query: str) -> Any:
            """Search Notion pages and databases the integration can access."""
            return self._request("POST", "/search", json={"query": query})

        def get_page(page_id: str) -> Any:
            """Retrieve a Notion page's properties by id."""
            return self._request("GET", f"/pages/{page_id}")

        def create_page(parent_database_id: str, title: str) -> Any:
            """Create a page in a database with the given title."""
            payload = {
                "parent": {"database_id": parent_database_id},
                "properties": {
                    "title": {"title": [{"text": {"content": title}}]}
                },
            }
            return self._request("POST", "/pages", json=payload)

        def query_database(database_id: str, page_size: int = 20) -> Any:
            """Query rows of a Notion database."""
            return self._request(
                "POST", f"/databases/{database_id}/query", json={"page_size": page_size}
            )

        def append_block(block_id: str, text: str) -> Any:
            """Append a paragraph block of text to a page or block."""
            payload = {
                "children": [
                    {
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [{"type": "text", "text": {"content": text}}]
                        },
                    }
                ]
            }
            return self._request("PATCH", f"/blocks/{block_id}/children", json=payload)

        return [
            StructuredTool.from_function(search, description=search.__doc__),
            StructuredTool.from_function(get_page, description=get_page.__doc__),
            StructuredTool.from_function(create_page, description=create_page.__doc__),
            StructuredTool.from_function(query_database, description=query_database.__doc__),
            StructuredTool.from_function(append_block, description=append_block.__doc__),
        ]
