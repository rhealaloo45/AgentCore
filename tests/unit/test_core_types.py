"""Unit tests for AgentResult, AgentState, and ProviderFactory error paths."""

import pytest

from roscoe import AgentResult, AgentRunner
from roscoe.core.state import AgentState
from roscoe.llm import ProviderFactory


def test_agent_result_defaults():
    r = AgentResult(output="hi", run_id="abc")
    assert r.output == "hi"
    assert r.run_id == "abc"
    assert r.total_tokens == 0
    assert r.cost_usd is None
    assert r.error is None
    assert r.status == "success"
    assert r.pending_action is None
    assert r.nodes_traversed == []


def test_agent_state_is_typeddict():
    # TypedDict instances are plain dicts at runtime
    state: AgentState = {"messages": []}
    assert state["messages"] == []


def test_provider_factory_unknown_provider():
    with pytest.raises(ValueError) as exc:
        ProviderFactory.get_llm({"provider": "made_up"})
    assert "made_up" in str(exc.value)
    assert "azure_openai" in str(exc.value)  # lists built-ins


def test_provider_factory_missing_provider_key():
    with pytest.raises(ValueError):
        ProviderFactory.get_llm({})


def test_azure_missing_keys_raises():
    with pytest.raises(ValueError) as exc:
        ProviderFactory.get_llm({"provider": "azure_openai", "deployment": "gpt-4o"})
    assert "endpoint" in str(exc.value)


def test_from_config_requires_model_block(tmp_path):
    cfg = tmp_path / "c.yaml"
    cfg.write_text("agent_name: test-agent\n")
    with pytest.raises(ValueError):
        AgentRunner.from_config(cfg, tools=[])
