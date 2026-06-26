"""HR agent tools.

Domain tools over the HR system's REST API (via roscoe's ``RESTConnector``) plus an
optional knowledge-memory lookup for policy documents. ``build_tools`` binds the
connector/knowledge into closures and returns ready-to-use tools for ``AgentRunner``.

SAP / SharePoint connectors swap in for the REST/knowledge sources at v0.2.0 without
changing the tool surface.
"""

from __future__ import annotations

from typing import Any

from roscoe.tools import tool


def build_tools(rest: Any, knowledge: Any | None = None) -> list:
    """Build HR tools bound to a REST connector (and optional knowledge memory)."""

    @tool
    def get_leave_balance(employee_id: str) -> dict:
        """Get an employee's remaining leave balance by employee id."""
        return rest._request("GET", f"/employees/{employee_id}/leave-balance")

    @tool
    def submit_leave_request(
        employee_id: str, start_date: str, end_date: str, reason: str = ""
    ) -> dict:
        """Submit a leave request (dates as YYYY-MM-DD). May require approval."""
        return rest._request(
            "POST",
            "/leave-requests",
            json={
                "employee_id": employee_id,
                "start_date": start_date,
                "end_date": end_date,
                "reason": reason,
            },
        )

    @tool
    def get_payslip(employee_id: str, month: str) -> dict:
        """Get an employee's payslip for a month (YYYY-MM)."""
        return rest._request("GET", f"/employees/{employee_id}/payslips/{month}")

    @tool
    def update_personal_details(employee_id: str, field: str, value: str) -> dict:
        """Update one personal detail field (e.g. phone, address) for an employee."""
        return rest._request(
            "PATCH", f"/employees/{employee_id}", json={field: value}
        )

    tools = [get_leave_balance, submit_leave_request, get_payslip, update_personal_details]

    if knowledge is not None:

        @tool
        def get_policy_document(query: str) -> list:
            """Search HR policy documents and return matching passages with their source."""
            return [
                {"text": d.page_content, "source": d.metadata.get("source", "unknown")}
                for d in knowledge.retrieve(query)
            ]

        tools.append(get_policy_document)

    return tools
