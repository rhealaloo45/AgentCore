"""The ``@tool`` decorator.

Thin wrapper over LangChain's ``StructuredTool.from_function`` that adds a
``description=`` keyword for ergonomics. We deliberately reuse LangChain's Pydantic
schema inference (from type hints + docstring) rather than re-implementing it, so a
decorated function becomes a first-class ``StructuredTool`` the agent can call.
"""

from __future__ import annotations

from typing import Any, Callable

from langchain_core.tools import StructuredTool


def tool(
    func: Callable[..., Any] | None = None,
    *,
    description: str | None = None,
    name: str | None = None,
) -> Any:
    """Turn a plain Python function into a LangChain ``StructuredTool``.

    Usage::

        @tool(description="Fetches price for a product SKU")
        def get_price(sku: str) -> dict:
            return {"sku": sku, "price": 1999}

    Both ``@tool`` (bare) and ``@tool(description=...)`` forms are supported. If no
    description is given, the function's docstring is used.

    Args:
        func: The function being decorated (supplied automatically in the bare form).
        description: Tool description shown to the LLM. Falls back to the docstring.
        name: Override the tool name. Defaults to the function name.

    Returns:
        A ``StructuredTool`` (or a decorator returning one, in the keyword form).
    """

    def build(fn: Callable[..., Any]) -> StructuredTool:
        desc = description or (fn.__doc__.strip() if fn.__doc__ else None)
        if not desc:
            raise ValueError(
                f"@tool on '{fn.__name__}' needs a description: pass "
                f"description=... or give the function a docstring."
            )
        return StructuredTool.from_function(
            func=fn,
            name=name or fn.__name__,
            description=desc,
        )

    # Bare form: @tool
    if callable(func):
        return build(func)
    # Keyword form: @tool(description=...)
    return build
