"""Unit tests for the @tool decorator."""

import pytest
from langchain_core.tools import StructuredTool

from roscoe.tools import tool


def test_keyword_form_metadata_and_schema():
    @tool(description="Fetches price for a product SKU")
    def get_price(sku: str) -> dict:
        return {"sku": sku, "price": 1999}

    assert isinstance(get_price, StructuredTool)
    assert get_price.name == "get_price"
    assert get_price.description == "Fetches price for a product SKU"
    # Pydantic schema inferred from the type hints
    assert "sku" in get_price.args
    assert get_price.args["sku"]["type"] == "string"


def test_tool_runs():
    @tool(description="Adds two numbers")
    def add(a: int, b: int) -> int:
        return a + b

    assert add.invoke({"a": 2, "b": 3}) == 5


def test_bare_form_uses_docstring():
    @tool
    def ping(name: str) -> str:
        """Returns a greeting."""
        return f"Hello {name}"

    assert isinstance(ping, StructuredTool)
    assert ping.description == "Returns a greeting."
    assert ping.invoke({"name": "Rhea"}) == "Hello Rhea"


def test_name_override():
    @tool(description="x", name="custom_name")
    def original(x: str) -> str:
        return x

    assert original.name == "custom_name"


def test_missing_description_raises():
    with pytest.raises(ValueError):

        @tool
        def no_desc(x: str) -> str:
            return x
