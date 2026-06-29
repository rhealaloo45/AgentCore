"""Unit tests for Phase 3 middleware: retry, cost, audit, rate limiter."""

import json
import time

import pytest
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage

from roscoe.middleware.audit_logger import AuditLogger
from roscoe.middleware.cost_tracker import calculate_cost, sum_usage
from roscoe.middleware.rate_limiter import RateLimiter, TokenBucket
from roscoe.middleware.retry import apply_retry, retriable_exceptions


# --- retry ---


def test_retriable_always_includes_connection_timeout():
    exc = retriable_exceptions("ollama")
    assert ConnectionError in exc
    assert TimeoutError in exc


def test_retriable_openai_adds_rate_limit():
    exc = retriable_exceptions("openai")
    names = {e.__name__ for e in exc}
    assert "RateLimitError" in names


def test_apply_retry_returns_runnable():
    llm = FakeMessagesListChatModel(responses=[AIMessage(content="x")])
    wrapped = apply_retry(llm, {"max_attempts": 3}, "openai")
    assert hasattr(wrapped, "invoke")


def test_apply_retry_disabled_returns_same():
    llm = FakeMessagesListChatModel(responses=[AIMessage(content="x")])
    assert apply_retry(llm, {"enabled": False}, "openai") is llm


# --- cost ---


def test_calculate_cost_known_model():
    # 1000 in @ 0.005, 1000 out @ 0.015 = 0.005 + 0.015 = 0.02
    cost = calculate_cost("azure_openai", "gpt-4o", 1000, 1000)
    assert cost == pytest.approx(0.02)


def test_calculate_cost_ollama_is_zero():
    assert calculate_cost("ollama", "qwen2.5", 5000, 5000) == 0.0


def test_calculate_cost_unknown_model_is_none():
    assert calculate_cost("openai", "mystery-model", 100, 100) is None


def test_sum_usage():
    class M:
        def __init__(self, i, o, t):
            self.usage_metadata = {"input_tokens": i, "output_tokens": o, "total_tokens": t}

    msgs = [M(10, 5, 15), M(20, 10, 30)]
    assert sum_usage(msgs) == (30, 15, 45)


# --- audit ---


def test_audit_writes_record(tmp_path):
    logger = AuditLogger(log_dir=tmp_path, filename="audit.jsonl")
    logger.log({"run_id": "r1", "status": "success"})
    logger.flush()
    lines = (tmp_path / "audit.jsonl").read_text().strip().splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["run_id"] == "r1"
    assert rec["status"] == "success"


def test_audit_has_required_fields(tmp_path):
    logger = AuditLogger(log_dir=tmp_path)
    record = {
        "run_id": "r2",
        "agent_name": "a",
        "user_id": None,
        "provider": "openai",
        "model": "gpt-4o",
        "start_time": "t0",
        "end_time": "t1",
        "total_tokens": 10,
        "cost_usd": 0.001,
        "nodes_traversed": [],
        "status": "success",
        "error": None,
    }
    logger.log(record)
    logger.flush()
    rec = json.loads((tmp_path / "audit.jsonl").read_text().strip())
    for key in record:
        assert key in rec


# --- rate limiter ---


def test_rate_limiter_skips_ollama():
    rl = RateLimiter()
    rl.configure("ollama", {"enabled": True, "requests_per_minute": 60})
    assert rl.active is False


def test_rate_limiter_configures_other_providers():
    rl = RateLimiter()
    rl.configure("openai", {"enabled": True, "requests_per_minute": 60})
    assert rl.active is True


async def test_rate_limiter_acquire_unconfigured_is_noop():
    rl = RateLimiter()
    await rl.acquire("openai")  # nothing configured -> returns immediately


async def test_token_bucket_allows_burst_up_to_capacity():
    bucket = TokenBucket(requests_per_minute=60)  # starts full (60 tokens)
    start = time.monotonic()
    for _ in range(5):
        await bucket.acquire()
    assert time.monotonic() - start < 0.1  # no waiting within capacity
