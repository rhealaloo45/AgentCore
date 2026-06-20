# roscoe

> Provider-agnostic LangChain agent framework with middleware and evals.

![CI](https://github.com/rhealaloo45/roscoe/actions/workflows/ci.yml/badge.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

A reusable Python SDK built on LangChain that bakes in the production plumbing —
auth, retries, cost tracking, audit logging, rate limiting — so each new agent
project starts production-ready. You write tools (plain Python) and a YAML config;
roscoe wires the rest.

```python
from roscoe import AgentRunner
from roscoe.tools import tool


@tool(description="Fetches price for a product SKU")
def get_price(sku: str) -> dict:
    return {"sku": sku, "price": 1999}


agent = AgentRunner.from_config("agent_config.yaml", tools=[get_price])
result = agent.run("What is the price of SKU-001?")

print(result.output)    # the answer
print(result.cost_usd)  # "$0.011"
print(result.run_id)    # uuid for audit trail
```

> **Status:** early development (`0.1.0.dev0`). See [PLAN.md](./PLAN.md) for the build roadmap.

## Development

```bash
pip install -e ".[dev]"
pytest -q
```

## License

MIT — see [LICENSE](./LICENSE).
