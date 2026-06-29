"""Retry middleware — provider-aware, applied per LLM call.

Retry is bound to the chat model (via LangChain's ``Runnable.with_retry``), not the
graph: a transient error retries just the LLM call instead of re-running every node.
Retriable error types are resolved per provider from each SDK (best-effort imports),
always including ``ConnectionError`` / ``TimeoutError``. Backoff is exponential with
jitter so concurrent agents don't retry in lockstep.
"""

from __future__ import annotations

from typing import Any

from langchain_core.language_models import BaseChatModel

# Always retriable, regardless of provider.
_ALWAYS: tuple[type[BaseException], ...] = (ConnectionError, TimeoutError)


def retriable_exceptions(provider: str) -> tuple[type[BaseException], ...]:
    """Return the exception types worth retrying for a provider.

    Uses best-effort imports of each provider SDK; if a package isn't installed,
    its specific errors are simply skipped (the ``_ALWAYS`` set still applies).
    """
    exc: list[type[BaseException]] = list(_ALWAYS)

    if provider in ("openai", "azure_openai"):
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
    elif provider == "gemini":
        try:
            from google.api_core.exceptions import (
                ResourceExhausted,
                ServiceUnavailable,
            )

            exc += [ResourceExhausted, ServiceUnavailable]
        except ImportError:
            pass
    elif provider == "anthropic":
        try:
            from anthropic import (
                APIConnectionError,
                InternalServerError,
                RateLimitError,
            )

            exc += [RateLimitError, APIConnectionError, InternalServerError]
        except ImportError:
            pass
    # ollama: connection/timeout only (covered by _ALWAYS)

    return tuple(dict.fromkeys(exc))  # de-dup, preserve order


def apply_retry(
    llm: BaseChatModel,
    config: dict[str, Any] | None,
    provider: str,
) -> BaseChatModel:
    """Wrap ``llm`` with retry behaviour from a middleware config block.

    Config keys: ``max_attempts`` (default 3), ``base_delay_seconds`` (default 1.5),
    ``jitter`` (default True). Returns the model unchanged if retry is disabled.
    """
    config = config or {}
    if config.get("enabled") is False:
        return llm

    max_attempts = int(config.get("max_attempts", 3))
    base_delay = float(config.get("base_delay_seconds", 1.5))
    jitter = bool(config.get("jitter", True))

    kwargs: dict[str, Any] = {
        "retry_if_exception_type": retriable_exceptions(provider),
        "stop_after_attempt": max_attempts,
        "wait_exponential_jitter": jitter,
    }
    # Newer langchain-core lets us tune the initial delay; ignore if unsupported.
    try:
        return llm.with_retry(
            exponential_jitter_params={"initial": base_delay}, **kwargs
        )
    except TypeError:
        return llm.with_retry(**kwargs)
