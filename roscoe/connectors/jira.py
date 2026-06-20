"""Jira connector — pre-built tools over the Jira Cloud REST API (v3).

Auth: Basic with an Atlassian account email + API token.

```yaml
connectors:
  jira:
    base_url: ${JIRA_URL}      # https://your-org.atlassian.net
    email: ${JIRA_EMAIL}
    api_token: ${JIRA_TOKEN}
```
"""

from __future__ import annotations

import base64
from typing import Any

from langchain_core.tools import StructuredTool

from roscoe.connectors.base_connector import BaseConnector

_API = "/rest/api/3"


class JiraConnector(BaseConnector):
    """Tools: create_issue, get_issue, update_issue, search_issues, add_comment."""

    def _base_url(self) -> str:
        url = self.config.get("base_url")
        if not url:
            raise ValueError("jira connector config missing required key 'base_url'.")
        return url.rstrip("/")

    def _auth_headers(self) -> dict[str, str]:
        for key in ("email", "api_token"):
            if not self.config.get(key):
                raise ValueError(f"jira connector config missing required key '{key}'.")
        raw = f"{self.config['email']}:{self.config['api_token']}".encode()
        return {
            "Authorization": f"Basic {base64.b64encode(raw).decode()}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    @property
    def tools(self) -> list[StructuredTool]:
        def create_issue(
            project_key: str, summary: str, description: str = "", issue_type: str = "Task"
        ) -> Any:
            """Create a Jira issue and return its key and id."""
            payload = {
                "fields": {
                    "project": {"key": project_key},
                    "summary": summary,
                    "description": _adf(description),
                    "issuetype": {"name": issue_type},
                }
            }
            return self._request("POST", f"{_API}/issue", json=payload)

        def get_issue(issue_key: str) -> Any:
            """Fetch a Jira issue by key (e.g. PROJ-123)."""
            return self._request("GET", f"{_API}/issue/{issue_key}")

        def update_issue(issue_key: str, fields: dict) -> Any:
            """Update fields on a Jira issue."""
            return self._request(
                "PUT", f"{_API}/issue/{issue_key}", json={"fields": fields}
            )

        def search_issues(jql: str, max_results: int = 20) -> Any:
            """Search Jira issues with a JQL query."""
            return self._request(
                "POST",
                f"{_API}/search",
                json={"jql": jql, "maxResults": max_results},
            )

        def add_comment(issue_key: str, body: str) -> Any:
            """Add a comment to a Jira issue."""
            return self._request(
                "POST", f"{_API}/issue/{issue_key}/comment", json={"body": _adf(body)}
            )

        return [
            StructuredTool.from_function(create_issue, description=create_issue.__doc__),
            StructuredTool.from_function(get_issue, description=get_issue.__doc__),
            StructuredTool.from_function(update_issue, description=update_issue.__doc__),
            StructuredTool.from_function(search_issues, description=search_issues.__doc__),
            StructuredTool.from_function(add_comment, description=add_comment.__doc__),
        ]


def _adf(text: str) -> dict:
    """Wrap plain text in Atlassian Document Format (required by Jira v3)."""
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": text or " "}]}
        ],
    }
