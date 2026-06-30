"""Retry middleware — provider-aware, applied per LLM call.

Retry is bound to the chat model (via LangChain's ``Runnable.with_retry``), not the
graph: a transient error retries just the LLM call instead of re-running every node.
Retriable error types are resolved per provider from each SDK (best-effort imports),
always including ``ConnectionError`` / ``TimeoutError``. Backoff is exponential with
jitter so concurrent agents don't retry in lockstep.

Daily quota exhaustion (e.g. Gemini free tier) is NOT retried — it won't recover
until the next day, so retrying only wastes time. Per-minute rate limits ARE retried.
"""

from __future__ import annotations

from typing import Any

from langchain_core.language_models import BaseChatModel

# Always retriable, regardless of provider.
_ALWAYS: tuple[type[BaseException], ...] = (ConnectionError, TimeoutError)

# Substrings that indicate a daily/total quota is gone — don't retry these.
_DAILY_QUOTA_MARKERS = (
    "perday",
    "per_day",
    "free-models-per-day",
    "daily",
    "quota_id",          # Google's structured quota violation messages
    "limit: 0",
)


def _is_daily_quota(exc: BaseException) -> bool:
    """Return True if the error is a daily/total quota exhaustion (not transient)."""
    msg = str(exc).lower()
    return any(m in msg for m in _DAILY_QUOTA_MARKERS)


def _should_retry(exc: BaseException) -> bool:
    """Retry predicate: yes for transient errors, no for daily quota exhaustion."""
    if _is_daily_quota(exc):
        return False
    return True


def retriable_exceptions(provider: str) -> tuple[type[BaseException], ...]:
    """Return the exception types worth retrying for a provider."""
    exc: list[type[BaseException]] = list(_ALWAYS)

    if provider in ("openai", "azure_openai"):
        try:
            from openai import (
                APIConnectionError,
                APIStatusError,
                APITimeoutError,
                InternalServerError,
                RateLimitError,
            )
            exc += [RateLimitError, APIConnectionError, APITimeoutError,
                    InternalServerError, APIStatusError]
        except ImportError:
            pass
    elif provider == "gemini":
        try:
            from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable
            exc += [ResourceExhausted, ServiceUnavailable]
        except ImportError:
            pass
    elif provider == "anthropic":
        try:
            from anthropic import APIConnectionError, InternalServerError, RateLimitError
            exc += [RateLimitError, APIConnectionError, InternalServerError]
        except ImportError:
            pass
    elif provider == "nvidia":
        # NVIDIA NIM uses an OpenAI-compatible REST API — reuse the same error types.
        try:
            from openai import (
                APIConnectionError,
                APITimeoutError,
                InternalServerError,
                RateLimitError,
            )
            exc += [RateLimitError, APIConnectionError, APITimeoutError, InternalServerError]
        except ImportError:
            pass

    return tuple(dict.fromkeys(exc))


def apply_retry(
    llm: BaseChatModel,
    config: dict[str, Any] | None,
    provider: str,
) -> BaseChatModel:
    """Wrap ``llm`` with retry behaviour from a middleware config block."""
    config = config or {}
    if config.get("enabled") is False:
        return llm

    max_attempts = int(config.get("max_attempts", 3))
    base_delay = float(config.get("base_delay_seconds", 1.5))
    jitter = bool(config.get("jitter", True))

    kwargs: dict[str, Any] = {
        "retry_if_exception_type": retriable_exceptions(provider),
        "retry_if_exception": _should_retry,
        "stop_after_attempt": max_attempts,
        "wait_exponential_jitter": jitter,
    }
    try:
        return llm.with_retry(
            exponential_jitter_params={"initial": base_delay}, **kwargs
        )
    except TypeError:
        # Older langchain-core — drop unsupported kwargs one by one
        for drop in ("retry_if_exception", "exponential_jitter_params"):
            kwargs.pop(drop, None)
            try:
                return llm.with_retry(**kwargs)
            except TypeError:
                continue
        return llm.with_retry(**kwargs)
