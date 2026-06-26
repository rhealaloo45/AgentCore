"""Phase 9 — template tests.

Templates are exercised with mocked connectors / a local keyword knowledge store, so no
live HR API, ServiceNow, or LLM is needed.
"""

import httpx
import pytest

from roscoe.connectors import RESTConnector, ServiceNowConnector
from roscoe.memory.knowledge import KnowledgeMemory
from roscoe.templates import available_templates, template_path
from roscoe.templates.hr_agent.tools.hr_tools import build_tools as build_hr_tools
from roscoe.templates.it_support_agent.tools.it_tools import build_tools as build_it_tools
from roscoe.templates.legal_agent.tools.legal_tools import build_tools as build_legal_tools


def _json(payload, status=200):
    return httpx.Response(status, json=payload)


# --- registry / packaging ---


def test_available_templates_and_files_exist():
    names = available_templates()
    assert set(names) == {"hr_agent", "it_support_agent", "legal_agent"}
    for name in names:
        d = template_path(name)
        assert (d / "agent_config.yaml").exists()
        assert (d / "prompts" / "system.txt").exists()


def test_template_path_unknown_raises():
    with pytest.raises(ValueError):
        template_path("nope_agent")


# --- HR template (REST connector, mocked) ---


def test_hr_get_leave_balance_via_rest():
    def handler(request):
        assert request.url.path == "/employees/E1/leave-balance"
        return _json({"employee_id": "E1", "remaining_days": 12})

    rest = RESTConnector(
        {"base_url": "https://hr.example.com", "auth": "bearer", "token": "t"},
        transport=httpx.MockTransport(handler),
    )
    tools = build_hr_tools(rest)
    names = {t.name for t in tools}
    assert {"get_leave_balance", "submit_leave_request", "get_payslip", "update_personal_details"} <= names

    get_balance = next(t for t in tools if t.name == "get_leave_balance")
    out = get_balance.invoke({"employee_id": "E1"})
    assert out["remaining_days"] == 12


def test_hr_policy_tool_added_with_knowledge():
    rest = RESTConnector(
        {"base_url": "https://hr.example.com", "auth": "bearer", "token": "t"},
        transport=httpx.MockTransport(lambda r: _json({})),
    )
    km = KnowledgeMemory.from_texts(
        ["Annual leave accrues at 1.75 days per month."],
        metadatas=[{"source": "leave_policy.pdf"}],
    )
    tools = build_hr_tools(rest, knowledge=km)
    policy = next(t for t in tools if t.name == "get_policy_document")
    hits = policy.invoke({"query": "leave accrual"})
    assert hits and hits[0]["source"] == "leave_policy.pdf"


# --- IT support template (ServiceNow, mocked) ---


def test_it_create_ticket_returns_number():
    def handler(request):
        assert request.url.path == "/api/now/table/incident"
        return _json({"result": {"number": "INC0012345", "sys_id": "abc123"}})

    snow = ServiceNowConnector(
        {"instance_url": "https://dev.service-now.com", "username": "a", "password": "b"},
        transport=httpx.MockTransport(handler),
    )
    tools = build_it_tools(snow)
    assert {t.name for t in tools} == {
        "create_ticket",
        "check_ticket_status",
        "escalate_ticket",
        "search_knowledge_base",
    }
    create = next(t for t in tools if t.name == "create_ticket")
    out = create.invoke({"short_description": "laptop won't boot"})
    assert out["number"] == "INC0012345"
    assert out["sys_id"] == "abc123"


# --- Legal template (knowledge memory, keyword store) ---


def test_legal_extract_clause_cites_source():
    km = KnowledgeMemory.from_texts(
        [
            "Limitation of liability: in no event shall either party's liability exceed fees paid.",
            "Term and termination: either party may terminate with 30 days notice.",
        ],
        metadatas=[{"source": "msa_acme.pdf"}, {"source": "msa_acme.pdf"}],
        top_k=2,
    )
    tools = build_legal_tools(km)
    assert {t.name for t in tools} == {
        "search_contracts",
        "extract_clause",
        "compare_documents",
        "flag_risk",
    }
    extract = next(t for t in tools if t.name == "extract_clause")
    out = extract.invoke({"clause_type": "liability"})
    assert out["found"]
    assert "liability" in out["text"].lower()
    assert out["source"] == "msa_acme.pdf"
