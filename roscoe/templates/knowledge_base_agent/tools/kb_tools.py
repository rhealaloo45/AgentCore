"""Knowledge-base agent tools.

Answers questions over internal documents in Notion and/or SharePoint, plus an optional
local knowledge-memory store. Reuses each connector's own (tested) tools rather than
re-deriving endpoints; ``build_tools`` curates the read-only subset and adds a cited
local-search tool. At least one source must be provided.
"""

from __future__ import annotations

from typing import Any

from roscoe.tools import tool

_NOTION_TOOLS = {"search", "get_page"}
_SHAREPOINT_TOOLS = {"search_documents", "get_document"}


def build_tools(
    notion: Any | None = None,
    sharepoint: Any | None = None,
    knowledge: Any | None = None,
) -> list:
    """Build doc-search tools from whichever sources are supplied."""
    if notion is None and sharepoint is None and knowledge is None:
        raise ValueError(
            "knowledge_base_agent needs at least one source: notion, sharepoint, or knowledge."
        )

    tools: list = []

    if knowledge is not None:

        @tool
        def search_knowledge(query: str) -> list:
            """Search the local knowledge base and return passages with their source."""
            return [
                {"text": d.page_content, "source": d.metadata.get("source", "unknown")}
                for d in knowledge.retrieve(query)
            ]

        tools.append(search_knowledge)

    if notion is not None:
        tools += [t for t in notion.tools if t.name in _NOTION_TOOLS]
    if sharepoint is not None:
        tools += [t for t in sharepoint.tools if t.name in _SHAREPOINT_TOOLS]

    return tools
