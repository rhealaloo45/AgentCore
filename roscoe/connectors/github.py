"""GitHub connector — pre-built tools over the GitHub REST API.

Auth: a personal access token (or GitHub App installation token) as a bearer.

```yaml
connectors:
  github:
    token: ${GITHUB_TOKEN}
    base_url: https://api.github.com   # optional; override for GitHub Enterprise
```

Repos are passed as ``owner/name`` (e.g. ``rhealaloo45/roscoe``).
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import StructuredTool

from roscoe.connectors.base_connector import BaseConnector


class GitHubConnector(BaseConnector):
    """Tools: get_issue, create_issue, search_issues, add_comment, get_file, list_repos."""

    def _base_url(self) -> str:
        return self.config.get("base_url", "https://api.github.com").rstrip("/")

    def _auth_headers(self) -> dict[str, str]:
        if not self.config.get("token"):
            raise ValueError("github connector config missing required key 'token'.")
        return {
            "Authorization": f"Bearer {self.config['token']}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    @property
    def tools(self) -> list[StructuredTool]:
        def get_issue(repo: str, number: int) -> Any:
            """Fetch an issue by number from a repo (repo = 'owner/name')."""
            return self._request("GET", f"/repos/{repo}/issues/{number}")

        def create_issue(repo: str, title: str, body: str = "") -> Any:
            """Open a new issue in a repo."""
            return self._request(
                "POST", f"/repos/{repo}/issues", json={"title": title, "body": body}
            )

        def search_issues(query: str) -> Any:
            """Search issues and PRs across GitHub with a search query."""
            return self._request("GET", "/search/issues", params={"q": query})

        def add_comment(repo: str, number: int, body: str) -> Any:
            """Add a comment to an issue or pull request."""
            return self._request(
                "POST", f"/repos/{repo}/issues/{number}/comments", json={"body": body}
            )

        def get_file(repo: str, path: str, ref: str = "main") -> Any:
            """Get the contents metadata of a file at a path on a branch/ref."""
            return self._request(
                "GET", f"/repos/{repo}/contents/{path}", params={"ref": ref}
            )

        def list_repos(org: str = "") -> Any:
            """List repositories for an org, or the authenticated user if org is empty."""
            path = f"/orgs/{org}/repos" if org else "/user/repos"
            return self._request("GET", path)

        return [
            StructuredTool.from_function(get_issue, description=get_issue.__doc__),
            StructuredTool.from_function(create_issue, description=create_issue.__doc__),
            StructuredTool.from_function(search_issues, description=search_issues.__doc__),
            StructuredTool.from_function(add_comment, description=add_comment.__doc__),
            StructuredTool.from_function(get_file, description=get_file.__doc__),
            StructuredTool.from_function(list_repos, description=list_repos.__doc__),
        ]
