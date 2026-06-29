"""SharePoint connector — pre-built tools over Microsoft Graph (app-only OAuth2).

Acts on one site's default document library. Same client-credentials auth as Outlook.

```yaml
connectors:
  sharepoint:
    client_id: ${SP_CLIENT_ID}
    client_secret: ${SP_CLIENT_SECRET}
    tenant_id: ${SP_TENANT_ID}
    site_id: ${SP_SITE_ID}        # Graph site id (host,siteCollectionId,siteId)
```

App-only access needs Sites.Read.All / Sites.ReadWrite.All with admin consent.
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import StructuredTool

from roscoe.connectors._graph_base import GraphConnector


class SharePointConnector(GraphConnector):
    """Tools: search_documents, get_document, list_files, upload_file."""

    extra_required = ("site_id",)

    @property
    def tools(self) -> list[StructuredTool]:
        site = self.config["site_id"]
        drive = f"/sites/{site}/drive"

        def search_documents(query: str) -> Any:
            """Search documents in the SharePoint site's document library."""
            return self._request("GET", f"{drive}/root/search(q='{query}')")

        def get_document(item_id: str) -> Any:
            """Get a document's metadata by drive item id."""
            return self._request("GET", f"{drive}/items/{item_id}")

        def list_files(folder_path: str = "") -> Any:
            """List files in a folder (root if no path given)."""
            if folder_path:
                return self._request("GET", f"{drive}/root:/{folder_path}:/children")
            return self._request("GET", f"{drive}/root/children")

        def upload_file(name: str, content: str) -> Any:
            """Upload a small text file to the library root."""
            return self._request(
                "PUT",
                f"{drive}/root:/{name}:/content",
                headers={"Content-Type": "text/plain"},
                content=content.encode("utf-8"),
            )

        return [
            StructuredTool.from_function(
                search_documents, description=search_documents.__doc__
            ),
            StructuredTool.from_function(get_document, description=get_document.__doc__),
            StructuredTool.from_function(list_files, description=list_files.__doc__),
            StructuredTool.from_function(upload_file, description=upload_file.__doc__),
        ]
