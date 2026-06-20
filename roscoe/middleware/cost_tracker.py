"""Cost tracker — per-run token counts → USD estimate.

Reads the provider-agnostic ``usage_metadata`` that LangChain attaches to each AI
message (input/output token counts) and prices it with ``COST_TABLE``. This is
provider-agnostic by design — it does NOT use the OpenAI-only ``get_openai_callback``,
so Anthropic/Gemini are covered too. Ollama is always $0.00.

``COST_TABLE`` is module-level and extensible: custom providers add their rates with
``COST_TABLE["my_provider"] = {...}`` and cost flows into ``AgentResult.cost_usd``.

Rates are per 1K tokens and best-effort — they drift; verify before relying on them.
Model ids are aliases (e.g. ``claude-sonnet-4-5``); confirm against the provider API.
"""

from __future__ import annotations

from typing import Any

# rates per 1K tokens: {provider: {model: {"input": x, "output": y}}}
COST_TABLE: dict[str, dict[str, dict[str, float]]] = {
    "azure_openai": {
        "gpt-4o": {"input": 0.005, "output": 0.015},
        "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    },
    "openai": {
        "gpt-4o": {"input": 0.005, "output": 0.015},
        "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    },
    "gemini": {
        "gemini-1.5-pro": {"input": 0.0035, "output": 0.0105},
    },
    "anthropic": {
        "claude-sonnet-4-5": {"input": 0.003, "output": 0.015},
    },
    "ollama": {},  # always $0.00
}


def sum_usage(messages: list[Any]) -> tuple[int, int, int]:
    """Sum (input, output, total) tokens across messages with usage_metadata."""
    inp = out = total = 0
    for msg in messages:
        usage = getattr(msg, "usage_metadata", None)
        if usage:
            inp += usage.get("input_tokens", 0)
            out += usage.get("output_tokens", 0)
            total += usage.get("total_tokens", 0)
    return inp, out, total


def calculate_cost(
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> float | None:
    """Compute USD cost from token counts, or ``None`` if the model isn't priced.

    Ollama (and any provider with an empty rate table) returns ``0.0``.
    """
    provider_rates = COST_TABLE.get(provider)
    if provider_rates is None:
        return None
    if provider == "ollama":
        return 0.0
    rates = provider_rates.get(model)
    if rates is None:
        return None
    cost = (input_tokens / 1000) * rates["input"] + (output_tokens / 1000) * rates["output"]
    return round(cost, 6)
