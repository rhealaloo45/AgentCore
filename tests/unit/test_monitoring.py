"""Phase 7 — monitoring tests.

Deterministic aggregation over mock audit records; alert boundaries; exporters and
notifier verified against mocked clients (no live Pushgateway / Slack / Azure).
"""

import json

import httpx
import pytest

from roscoe.monitoring import (
    aggregate,
    check_and_notify,
    evaluate_alerts,
    load_audit,
    render,
)
from roscoe.monitoring.exporters.azure_monitor import AzureMonitorExporter
from roscoe.monitoring.exporters.prometheus import PrometheusPushgatewayExporter
from roscoe.monitoring.notifier import Notifier, SlackNotifier


def _rec(**kw):
    base = {
        "run_id": "r",
        "agent_name": "hr",
        "user_id": "u1",
        "start_time": "2026-06-27T10:00:00+00:00",
        "end_time": "2026-06-27T10:00:01+00:00",  # 1000 ms
        "total_tokens": 100,
        "cost_usd": 0.01,
        "status": "success",
        "error": None,
    }
    base.update(kw)
    return base


# --- aggregation ---


def test_aggregate_costs_tokens_and_status():
    records = [
        _rec(cost_usd=0.01, total_tokens=100),
        _rec(cost_usd=0.02, total_tokens=200, agent_name="legal", user_id="u2"),
        _rec(status="error", error="ValueError: bad", cost_usd=0.0, total_tokens=0),
    ]
    m = aggregate(records)
    assert m.total_runs == 3
    assert m.runs_by_status == {"success": 2, "error": 1}
    assert m.total_cost_usd == 0.03
    assert m.cost_by_agent["hr"] == 0.01
    assert m.cost_by_agent["legal"] == 0.02
    assert m.cost_by_user["u2"] == 0.02
    assert m.cost_by_day["2026-06-27"] == 0.03
    assert m.tokens_by_day["2026-06-27"] == 300
    assert m.error_rate_pct == round(100 / 3, 2)
    assert m.errors_by_type == {"ValueError": 1}


def test_aggregate_latency_percentiles():
    # latencies 1000ms x4, 5000ms x1 for agent hr
    records = [_rec() for _ in range(4)]
    records.append(_rec(end_time="2026-06-27T10:00:05+00:00"))  # 5000 ms
    m = aggregate(records)
    lat = m.latency_ms_by_agent["hr"]
    assert lat["count"] == 5
    assert lat["p50"] == 1000.0
    assert lat["p99"] > 1000.0  # pulled up by the 5000ms outlier
    assert m.max_p95_latency_ms == lat["p95"]


def test_aggregate_empty():
    m = aggregate([])
    assert m.total_runs == 0
    assert m.error_rate_pct == 0.0
    assert m.total_cost_usd == 0.0


def test_load_audit_skips_blank_and_bad_lines(tmp_path):
    p = tmp_path / "audit.jsonl"
    p.write_text(json.dumps(_rec()) + "\n\nnot-json\n" + json.dumps(_rec()) + "\n")
    records = load_audit(p)
    assert len(records) == 2


def test_load_audit_missing_file(tmp_path):
    assert load_audit(tmp_path / "nope.jsonl") == []


# --- alerts (boundary) ---


def test_alert_fires_above_threshold_not_at_it():
    m = aggregate([_rec(cost_usd=10.0)])
    # exactly at threshold -> no alert (strict >)
    assert evaluate_alerts(m, {"daily_cost_usd": 10.0}) == []
    # below threshold -> fires
    fired = evaluate_alerts(m, {"daily_cost_usd": 9.99})
    assert len(fired) == 1
    assert fired[0].rule == "daily_cost_usd"
    assert "exceeded" in fired[0].message


def test_alert_error_rate_and_latency():
    records = [_rec(status="error", error="X: y"), _rec()]  # 50% error
    m = aggregate(records)
    fired = evaluate_alerts(m, {"error_rate_pct": 5.0, "latency_p95_ms": 100})
    rules = {a.rule for a in fired}
    assert "error_rate_pct" in rules
    assert "latency_p95_ms" in rules


def test_check_and_notify_sends_each_alert():
    sent = []

    class Spy(Notifier):
        def send(self, subject, body):
            sent.append((subject, body))

    m = aggregate([_rec(cost_usd=100.0)])
    fired = check_and_notify(m, {"daily_cost_usd": 1.0}, notifier=Spy())
    assert len(fired) == 1
    assert len(sent) == 1
    assert "daily_cost_usd" in sent[0][0]


# --- dashboard ---


def test_render_contains_headline_numbers():
    m = aggregate([_rec(), _rec(status="error", error="E: x")])
    out = render(m)
    assert "roscoe monitor" in out
    assert "runs: 2" in out
    assert "cost by agent" in out


# --- prometheus exporter (mocked transport) ---


def test_prometheus_pushes_text_format():
    seen = {}

    def handler(request):
        seen["path"] = request.url.path
        seen["body"] = request.content.decode()
        seen["ctype"] = request.headers.get("content-type")
        return httpx.Response(200)

    exp = PrometheusPushgatewayExporter(
        "https://pgw.example.com", transport=httpx.MockTransport(handler)
    )
    m = aggregate([_rec(cost_usd=0.05)])
    exp.export(m)
    assert seen["path"] == "/metrics/job/roscoe"
    assert "roscoe_runs_total 1" in seen["body"]
    assert "roscoe_cost_usd_total 0.05" in seen["body"]
    assert 'roscoe_latency_ms{agent="hr",quantile="p95"}' in seen["body"]
    assert "text/plain" in seen["ctype"]


def test_prometheus_requires_url():
    with pytest.raises(ValueError):
        PrometheusPushgatewayExporter("")


# --- slack notifier (mocked transport) ---


def test_slack_notifier_posts_text():
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content.decode())
        return httpx.Response(200)

    n = SlackNotifier("https://hooks.slack.com/x", transport=httpx.MockTransport(handler))
    n.send("subj", "hello")
    assert "subj" in seen["body"]["text"]
    assert "hello" in seen["body"]["text"]


# --- azure exporter (injected meter, no SDK) ---


def test_azure_exporter_records_via_injected_meter():
    calls = []

    class FakeGauge:
        def __init__(self, name):
            self.name = name

        def set(self, value, attributes):
            calls.append((self.name, value, attributes))

    class FakeMeter:
        def create_gauge(self, name):
            return FakeGauge(name)

    exp = AzureMonitorExporter(meter=FakeMeter())
    exp.export(aggregate([_rec(cost_usd=0.02)]))
    names = {c[0] for c in calls}
    assert "roscoe.runs_total" in names
    assert "roscoe.cost_usd_total" in names
    assert any(c[0] == "roscoe.cost_usd_by_agent" for c in calls)


def test_azure_exporter_missing_conn_and_meter():
    with pytest.raises(ValueError):
        AzureMonitorExporter()
