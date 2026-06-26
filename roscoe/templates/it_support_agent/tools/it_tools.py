"""IT support agent tools.

Domain tools over ServiceNow (via roscoe's ``ServiceNowConnector``) plus an optional
knowledge-memory lookup for the internal KB. ``build_tools`` binds the connector into
closures. Confluence swaps in for the KB at v0.2.0.
"""

from __future__ import annotations

from typing import Any

from roscoe.tools import tool

_INCIDENT = "/api/now/table/incident"


def build_tools(servicenow: Any, knowledge: Any | None = None) -> list:
    """Build IT support tools bound to a ServiceNow connector (and optional KB memory)."""

    @tool
    def create_ticket(short_description: str, description: str = "", urgency: str = "3") -> dict:
        """Create a ServiceNow incident. urgency: 1=high, 2=medium, 3=low. May require approval."""
        resp = servicenow._request(
            "POST",
            _INCIDENT,
            json={
                "short_description": short_description,
                "description": description,
                "urgency": urgency,
            },
        )
        result = resp.get("result", resp)
        return {"number": result.get("number"), "sys_id": result.get("sys_id")}

    @tool
    def check_ticket_status(number: str) -> dict:
        """Look up the current state of an incident by its number (e.g. INC0010001)."""
        resp = servicenow._request(
            "GET", _INCIDENT, params={"sysparm_query": f"number={number}"}
        )
        rows = resp.get("result", [])
        return rows[0] if rows else {"error": f"No incident {number} found."}

    @tool
    def escalate_ticket(sys_id: str) -> dict:
        """Escalate an incident to high urgency/priority by its sys_id."""
        resp = servicenow._request(
            "PATCH", f"{_INCIDENT}/{sys_id}", json={"urgency": "1", "priority": "1"}
        )
        return resp.get("result", resp)

    @tool
    def search_knowledge_base(query: str) -> list:
        """Search the IT knowledge base for articles relevant to the query."""
        if knowledge is not None:
            return [
                {"text": d.page_content, "source": d.metadata.get("source", "kb")}
                for d in knowledge.retrieve(query)
            ]
        resp = servicenow._request(
            "GET", "/api/now/table/kb_knowledge",
            params={"sysparm_query": f"textLIKE{query}"},
        )
        return resp.get("result", [])

    return [create_ticket, check_ticket_status, escalate_ticket, search_knowledge_base]
