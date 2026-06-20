"""Unit tests for Phase 5 connectors — mocked HTTP, no live APIs."""

import httpx

from roscoe.connectors import (
    JiraConnector,
    OutlookConnector,
    RESTConnector,
    ServiceNowConnector,
)


def _json(payload, status=200):
    return httpx.Response(status, json=payload)


# --- REST ---


def test_rest_get_sends_auth_and_returns_json():
    seen = {}

    def handler(request):
        seen["auth"] = request.headers.get("authorization")
        seen["path"] = request.url.path
        return _json({"ok": True})

    conn = RESTConnector(
        {"base_url": "https://api.example.com", "auth": "bearer", "token": "t0ken"},
        transport=httpx.MockTransport(handler),
    )
    names = {t.name for t in conn.tools}
    assert names == {"rest_get", "rest_post", "rest_put", "rest_delete"}

    get_tool = next(t for t in conn.tools if t.name == "rest_get")
    result = get_tool.invoke({"path": "/things"})
    assert result == {"ok": True}
    assert seen["auth"] == "Bearer t0ken"
    assert seen["path"] == "/things"


# --- Jira ---


def test_jira_create_issue_hits_correct_endpoint():
    seen = {}

    def handler(request):
        seen["path"] = request.url.path
        seen["auth"] = request.headers.get("authorization", "")
        return _json({"key": "PROJ-1", "id": "10001"})

    conn = JiraConnector(
        {"base_url": "https://org.atlassian.net", "email": "a@b.com", "api_token": "x"},
        transport=httpx.MockTransport(handler),
    )
    assert {t.name for t in conn.tools} == {
        "create_issue",
        "get_issue",
        "update_issue",
        "search_issues",
        "add_comment",
    }
    create = next(t for t in conn.tools if t.name == "create_issue")
    out = create.invoke({"project_key": "PROJ", "summary": "Bug"})
    assert out["key"] == "PROJ-1"
    assert seen["path"] == "/rest/api/3/issue"
    assert seen["auth"].startswith("Basic ")


# --- ServiceNow ---


def test_servicenow_get_ticket_status():
    def handler(request):
        assert request.url.path == "/api/now/table/incident"
        return _json({"result": [{"number": "INC0010001", "state": "2"}]})

    conn = ServiceNowConnector(
        {
            "instance_url": "https://dev.service-now.com",
            "username": "admin",
            "password": "pw",
        },
        transport=httpx.MockTransport(handler),
    )
    assert {t.name for t in conn.tools} == {
        "create_ticket",
        "update_ticket",
        "get_ticket_status",
        "search_kb",
    }
    tool = next(t for t in conn.tools if t.name == "get_ticket_status")
    out = tool.invoke({"number": "INC0010001"})
    assert out["result"][0]["number"] == "INC0010001"


# --- Outlook (OAuth2 token + Graph) ---


def test_outlook_acquires_token_then_sends_mail():
    calls = []

    def handler(request):
        host = request.url.host
        calls.append((host, request.url.path))
        if host == "login.microsoftonline.com":
            return _json({"access_token": "tok-123", "expires_in": 3600})
        # graph request must carry the bearer token
        assert request.headers.get("authorization") == "Bearer tok-123"
        return _json({"status": "sent"})

    conn = OutlookConnector(
        {
            "client_id": "cid",
            "client_secret": "secret",
            "tenant_id": "tid",
            "mailbox": "bot@org.com",
        },
        transport=httpx.MockTransport(handler),
    )
    assert {t.name for t in conn.tools} == {
        "send_email",
        "read_emails",
        "create_calendar_event",
        "get_availability",
    }
    send = next(t for t in conn.tools if t.name == "send_email")
    out = send.invoke({"to": "x@y.com", "subject": "Hi", "body": "Hello"})
    assert out == {"status": "sent"}
    # token endpoint hit first, then the Graph sendMail endpoint
    assert calls[0][0] == "login.microsoftonline.com"
    assert calls[1][1] == "/v1.0/users/bot@org.com/sendMail"


def test_outlook_missing_config_raises():
    import pytest

    with pytest.raises(ValueError):
        OutlookConnector({"client_id": "cid"})
