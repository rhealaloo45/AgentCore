# roscoe

> Provider-agnostic agent SDK — built on LangChain, with the production plumbing baked in.

![CI](https://github.com/rhealaloo45/roscoe/actions/workflows/ci.yml/badge.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

A reusable Python SDK that bakes in the production plumbing — retries, cost tracking,
audit logging, rate limiting, human approval, memory, monitoring, and evals — so each new
agent project starts production-ready. You write tools (plain Python) and a YAML config;
roscoe wires the rest. Switch LLM providers by editing one config block — your code never
changes.

roscoe runs its **own** async ReAct loop (no LangGraph dependency), which keeps the agent
loop small, transparent, and makes human-in-the-loop a simple pause/resume.

## Quick start

```python
from roscoe import AgentRunner
from roscoe.tools import tool


@tool
def get_price(sku: str) -> dict:
    """Fetch the price for a product SKU."""
    return {"sku": sku, "price": 1999}


agent = AgentRunner.from_config("agent_config.yaml", tools=[get_price])
result = agent.run("What is the price of SKU-001?")

print(result.output)      # the answer
print(result.cost_usd)    # estimated cost
print(result.run_id)      # uuid tying it to the audit trail
```

Or scaffold a project with the CLI:

```bash
roscoe init my-agent                          # blank project
roscoe init my-hr-bot --template hr_agent     # from a template
```

## What's in the box

- **Provider-agnostic** — Azure OpenAI, OpenAI (incl. OpenAI-compatible endpoints like
  OpenRouter via `base_url`), Gemini, Anthropic, Ollama. Swap via the `model:` config block.
  Register custom providers with `ProviderFactory.register()`.
- **Middleware, automatic** — per-call retry (provider-aware), cost tracking, non-blocking
  audit logging, and per-provider rate limiting on every run.
- **Memory** — conversation (windowed), persistent facts (sqlite), and knowledge/RAG
  (FAISS or a dependency-free keyword retriever).
- **8 connectors** — REST, Jira, ServiceNow, Outlook, SharePoint, GitHub, Notion, Snowflake.
  Each is `Connector(config).tools` → hand straight to `AgentRunner`.
- **Human-in-the-loop** — list tools under `require_approval_for`; the run pauses
  (`status="paused"`) and you `resume(run_id, "approve"|"reject"|"modify")`.
- **Monitoring** — offline aggregation of audit logs (cost, latency p50/p95/p99, error
  rates) + `roscoe monitor`; optional Prometheus Pushgateway / Azure Monitor exporters.
- **Evals** — dataset + scorers (tool-usage, LLM-as-judge quality, hallucination) +
  `compare_runs()` regression diffing + `roscoe eval`.
- **5 templates** — `hr_agent`, `it_support_agent`, `legal_agent`, `knowledge_base_agent`,
  `exec_assistant_agent`.

## Install

```bash
pip install -e .                 # core
pip install -e ".[dev]"          # + pytest
pip install -e ".[snowflake]"    # + Snowflake driver
pip install -e ".[azure]"        # + Azure Monitor exporter
```

> roscoe is not on PyPI yet (`0.1.0.dev0`). Install from source for now.

## CLI

```bash
roscoe init <name> [--template <t>]   # scaffold a project
roscoe monitor [--path logs/audit.jsonl]   # dashboard from audit logs
roscoe eval --dataset cases.json --config agent.yaml [--judge]
```

## Development

```bash
pip install -e ".[dev]"
pytest -q
```

## License

MIT — see [LICENSE](./LICENSE).
