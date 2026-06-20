"""End-to-end integration test: YAML -> run -> AgentResult.

Requires real Azure OpenAI credentials, so it skips automatically when they're
absent (the CI default). Set AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_KEY, and
AZURE_OPENAI_DEPLOYMENT to run it.
"""

import os

import pytest

from roscoe import AgentRunner
from roscoe.tools import tool

_REQUIRED = ("AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_KEY", "AZURE_OPENAI_DEPLOYMENT")

pytestmark = pytest.mark.skipif(
    not all(os.getenv(k) for k in _REQUIRED),
    reason="Azure OpenAI credentials not set; skipping live e2e test.",
)


def test_end_to_end(tmp_path):
    cfg = tmp_path / "agent_config.yaml"
    cfg.write_text(
        """
        agent_name: e2e-test-agent
        model:
          provider: azure_openai
          deployment: ${AZURE_OPENAI_DEPLOYMENT}
          endpoint: ${AZURE_OPENAI_ENDPOINT}
          api_key: ${AZURE_OPENAI_KEY}
        """
    )

    @tool(description="Returns the price for a product SKU")
    def get_price(sku: str) -> dict:
        return {"sku": sku, "price": 1999}

    agent = AgentRunner.from_config(cfg, tools=[get_price])
    result = agent.run("What is the price of SKU-001?")

    assert result.error is None
    assert result.status == "success"
    assert result.output != ""
    assert result.run_id
    assert result.total_tokens > 0
