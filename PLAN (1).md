# roscoe — Build Plan

> Provider-agnostic LangChain agent framework with middleware and evals.

---

## What This Is

A reusable Python SDK built on top of LangChain that solves the "boring but critical" parts of
building production agents — auth, retries, cost tracking, audit logging, rate limiting — so every
new agent project starts from a production-ready base instead of rebuilding plumbing from scratch.

Developers describe their agent in a YAML file, write their tools in plain Python, and get back a
fully wired agent with enterprise middleware already baked in.

```python
# what using this SDK looks like
from roscoe import AgentRunner
from roscoe.tools import tool

@tool(description="Fetches price for a product SKU")
def get_price(sku: str) -> dict:
    return {"sku": sku, "price": 1999}

agent = AgentRunner.from_config("agent_config.yaml", tools=[get_price])
result = agent.run("What is the price of SKU-001?")

print(result.output)      # the answer
print(result.cost_usd)    # "$0.011"
print(result.run_id)      # uuid for audit trail
```

---

## The Two-Layer Mental Model

```
Layer 2 — Developer's App         tools/ + prompts/ + main.py
                                  (pure business logic, no framework knowledge)
                                          ↓
Layer 1 — Enterprise SDK          auth, audit, retry, cost, rate limiting
                                  (how it runs safely in production)
```

The developer handles **what the agent does**.  
The SDK handles **how it runs in production**.  
Clean separation of concerns.

---

## Why Not Just Use OpenAI Agents SDK / LangChain Directly?

| | OpenAI Agents SDK | Raw LangChain | **roscoe** |
|---|---|---|---|
| Agent orchestration | ✅ | ✅ | ✅ (built on LangChain) |
| Azure AD / enterprise auth | ❌ | Manual every project | ✅ API key now; AAD (managed identity / client-credentials) planned v0.2.0 |
| Async retry with jitter | Basic | Manual every project | ✅ baked in |
| Per-run cost tracking | ❌ | Manual every project | ✅ baked in |
| Compliance-grade audit log | ❌ | ❌ | ✅ baked in |
| Provider swap via YAML | ❌ (OpenAI only) | Manual | ✅ one config line |
| Ollama local support | ❌ | Manual setup | ✅ baked in |
| Plug in your own provider | ❌ | Manual every project | ✅ `ProviderFactory.register()` |
| Automated eval suite | ❌ | ❌ | ✅ built in |
| Existing LangChain projects | Must rewrite | N/A | Drop-in adoption |

---

## Tech Stack

```
Orchestration     LangChain 0.3.25 + LangGraph 0.2.60   — pinned, not floating
Providers         langchain-openai, langchain-google-genai,
                  langchain-anthropic, langchain-ollama
Config            PyYAML 6.0.2 + Pydantic 2.10.6
Async             async-first core; sync run() wraps arun() via asyncio.run
HITL/persist      LangGraph checkpointer (SQLite dev / Postgres prod)
Approval receiver FastAPI + uvicorn (optional, opt-in for Slack buttons)
Monitoring        prometheus_client (Pushgateway) + azure-monitor-opentelemetry
Connectors        httpx (REST/Graph) + snowflake-connector-python (optional extra)
CLI               Click 8.1.8
Testing           pytest + pytest-asyncio
Packaging         Poetry + PyPI
CI                GitHub Actions
Docs              MkDocs Material (Phase 6)
```

**Rule: pin `langchain` and `langgraph` to exact versions** (they break on minor bumps). Let
`langchain-core` and the provider adapters (`langchain-openai`, etc.) float within their
compatible ranges — exact-pinning all of them at once produces an unsolvable resolver graph,
since each adapter pins its own `langchain-core` range. `poetry.lock` (committed) guarantees
reproducibility regardless. Upgrade only after the full eval suite passes.

---

## Folder Structure

```
roscoe/
├── pyproject.toml
├── poetry.lock                        ← committed, guarantees reproducibility
├── README.md
├── LICENSE                            ← MIT
├── PLAN.md                            ← this file
├── .github/
│   └── workflows/
│       └── ci.yml                     ← pytest on every push
│
├── roscoe/
│   ├── __init__.py                    ← exposes AgentRunner at top level
│   ├── core/
│   │   ├── agent_base.py              ← abstract base all agents inherit from
│   │   ├── agent_runner.py            ← AgentRunner.from_config() — main entry point
│   │   ├── agent_result.py            ← AgentResult dataclass
│   │   └── state.py                   ← base AgentState TypedDict
│   ├── config/
│   │   └── loader.py                  ← YAML loader with ${ENV_VAR} resolution
│   ├── tools/
│   │   └── decorator.py               ← @tool decorator (fn → StructuredTool)
│   ├── llm/
│   │   ├── base_provider.py           ← BaseProvider interface for custom providers
│   │   ├── provider_factory.py        ← ProviderFactory.get_llm() + register()
│   │   └── capability_map.py          ← tool_calling / streaming support per provider
│   ├── middleware/
│   │   ├── retry.py                   ← async retry with jitter, provider-aware errors
│   │   ├── cost_tracker.py            ← per-run token count + cost estimate
│   │   ├── audit_logger.py            ← non-blocking audit log (thread + queue + atexit flush)
│   │   ├── rate_limiter.py            ← token bucket, per-provider limits
│   │   └── human_approval.py          ← LangGraph interrupt() gate; suspend → resume()
│   ├── approval/
│   │   └── receiver.py                ← optional FastAPI: /slack/actions → resume() (opt-in)
│   ├── memory/
│   │   ├── conversation.py            ← in-session chat history memory
│   │   ├── persistent.py              ← cross-session memory (DB backed)
│   │   └── knowledge.py               ← RAG-style domain knowledge memory
│   ├── connectors/                    ← class-based: Connector(config).tools → AgentRunner
│   │   ├── base_connector.py          ← BaseConnector (httpx client + auth, transport-injectable)
│   │   ├── _graph_base.py             ← shared MS Graph OAuth2 base (Outlook + SharePoint)
│   │   ├── rest_api.py                ← generic configurable REST API connector
│   │   ├── jira.py                    ← Jira Cloud REST v3 (basic auth)
│   │   ├── servicenow.py             ← ServiceNow Table API (basic auth)
│   │   ├── outlook.py                 ← MS Graph mail/calendar (OAuth2 client-credentials)
│   │   ├── sharepoint.py             ← MS Graph documents (OAuth2 client-credentials)
│   │   ├── github.py                  ← GitHub REST (PAT bearer)
│   │   ├── notion.py                  ← Notion REST (token + version header)
│   │   ├── snowflake.py              ← SQL via optional driver (pip install "roscoe[snowflake]")
│   │   │                              ← confluence / sap: deferred to v0.2.0
│   ├── monitoring/
│   │   ├── metrics.py                 ← offline log aggregation (cost, latency, error rates)
│   │   ├── alerts.py                  ← threshold rules → notifier (reuse Phase 6)
│   │   └── exporters/
│   │       ├── azure_monitor.py       ← azure-monitor-opentelemetry push
│   │       └── prometheus.py          ← Pushgateway push; /metrics under `roscoe serve`
│   ├── templates/
│   │   ├── hr_agent/
│   │   │   ├── agent_config.yaml      ← pre-built HR agent config
│   │   │   ├── tools/hr_tools.py      ← HR-specific tool implementations
│   │   │   └── prompts/system.txt     ← HR agent system prompt
│   │   ├── it_support_agent/
│   │   │   ├── agent_config.yaml
│   │   │   ├── tools/it_tools.py
│   │   │   └── prompts/system.txt
│   │   └── legal_agent/
│   │       ├── agent_config.yaml
│   │       ├── tools/legal_tools.py
│   │       └── prompts/system.txt
│   ├── evals/
│   │   ├── eval_runner.py             ← EvalRunner — runs a suite of test cases
│   │   ├── dataset.py                 ← loads test_cases.json
│   │   ├── report.py                  ← generates eval report with pass/fail
│   │   └── scorers/
│   │       ├── output_quality.py      ← LLM-as-judge quality score
│   │       ├── hallucination.py       ← checks claims vs retrieved docs
│   │       ├── tool_usage.py          ← checks tool call sequence vs expected
│   │       └── regression.py          ← diffs two eval runs
│   └── cli/
│       └── init_command.py            ← roscoe init my-project
│
├── examples/
│   ├── hr_policy_agent/               ← Azure Search, policy Q&A
│   ├── legal_rag_agent/               ← citation grounding, contradiction detection
│   └── it_support_agent/             ← ServiceNow ticketing, approval workflow (HITL)
│
├── tests/
│   ├── unit/                          ← config loader, @tool, middleware (no LLM)
│   └── integration/                   ← full end-to-end (needs real API keys)
│
└── docs/
    └── index.md
```

---

## Provider Support

```yaml
# Azure OpenAI (enterprise default)
# v0.1.0 authenticates via api_key. Azure AD token auth (managed identity /
# client-credentials) is a v0.2.0 item.
model:
  provider: azure_openai
  deployment: gpt-4o
  endpoint: ${AZURE_OPENAI_ENDPOINT}
  api_key: ${AZURE_OPENAI_KEY}

# OpenAI direct
model:
  provider: openai
  model: gpt-4o
  api_key: ${OPENAI_API_KEY}

# Google Gemini
model:
  provider: gemini
  model: gemini-1.5-pro
  api_key: ${GOOGLE_API_KEY}

# Anthropic
model:
  provider: anthropic
  model: claude-sonnet-4-5
  api_key: ${ANTHROPIC_API_KEY}

# Ollama (local, free, no internet)
model:
  provider: ollama
  model: qwen2.5              # or gemma3, llama3.2
  base_url: http://localhost:11434
```

Provider is **the only config change** needed to switch models. All tools, prompts, and agent
logic stay identical.

### Provider Capability Map

| Provider | Tool calling | Streaming | Cost tracking | Rate limiting |
|---|---|---|---|---|
| Azure OpenAI | ✅ | ✅ | ✅ | ✅ |
| OpenAI | ✅ | ✅ | ✅ | ✅ |
| Gemini | ✅ | ✅ | ✅ | ✅ |
| Anthropic | ✅ | ✅ | ✅ | ✅ |
| Ollama | ✅ (model-dependent) | ✅ | ❌ ($0.00) | ❌ (local) |
| Custom | declared by user | declared by user | opt-in | opt-in |

> **Streaming** is surfaced via `arun()` / an async event stream, not through the final
> `AgentResult` returned by the synchronous `run()`.

---

## Custom Providers

Users can register any LangChain-compatible LLM as a first-class provider.
After registration it works identically to the built-in five — same YAML config,
same middleware, same evals. No changes to the rest of the codebase needed.

There are two scenarios depending on whether the LLM already has a LangChain wrapper:

```
Does your LLM have an existing LangChain wrapper?
(e.g. langchain-openai, langchain-huggingface, langchain-ollama, etc.)

YES → skip to Step 2
NO  → start at Step 1 (write the wrapper first)
```

---

### Step 1 — Write a LangChain Wrapper (only if needed)

If their LLM is a plain HTTP API with no LangChain support, wrap it first.
This is the only technically hard step.

```python
# my_project/wrappers/company_llm.py

from typing import Any, Iterator
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessage, AIMessageChunk
from langchain_core.outputs import ChatResult, ChatGeneration
import requests


class CompanyLLM(BaseChatModel):
    """LangChain wrapper for Company's internal LLM API."""

    endpoint: str
    api_key: str
    model: str = "company-gpt-v2"
    temperature: float = 0.1

    @property
    def _llm_type(self) -> str:
        return "company_llm"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        **kwargs: Any
    ) -> ChatResult:
        # convert LangChain messages to whatever format the API expects.
        # NOTE: msg.type is "human"/"ai"/"system" — map to the API's roles explicitly;
        # most OpenAI-compatible APIs want "user"/"assistant"/"system".
        role_map = {"human": "user", "ai": "assistant", "system": "system"}
        payload = {
            "model": self.model,
            "temperature": self.temperature,
            "messages": [
                {"role": role_map.get(msg.type, "user"), "content": msg.content}
                for msg in messages
            ]
        }
        response = requests.post(
            self.endpoint,
            json=payload,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=30
        )
        response.raise_for_status()
        data = response.json()

        # convert the API response back to a LangChain AIMessage
        content = data["choices"][0]["message"]["content"]
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=content))])

    # optional — only implement if the API supports streaming
    def _stream(self, messages, **kwargs) -> Iterator[AIMessageChunk]:
        pass
```

> **Async note:** this example uses blocking `requests` + sync `_generate`, so the async-first
> core will run it in a thread-pool executor (works, but no true concurrency). For a hot path,
> also implement `async def _agenerate(...)` with an async HTTP client (httpx/aiohttp).

**Shortcut:** If the LLM API is OpenAI-compatible (vLLM, Together AI, Groq, most
modern providers), skip the custom wrapper entirely and use `ChatOpenAI` with a
custom `base_url`:

```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    model="company-gpt-v2",
    base_url="https://my-company-llm.internal/v1",
    api_key="my-key"
)
# if this works, Step 1 is done — no custom wrapper needed
```

---

### Step 2 — Implement `BaseProvider`

Wrap the LLM (custom or existing) in a `BaseProvider`:

```python
# my_project/providers/company_provider.py

from roscoe.llm import BaseProvider
from langchain_core.language_models import BaseChatModel
from my_project.wrappers.company_llm import CompanyLLM


class CompanyLLMProvider(BaseProvider):

    def get_llm(self, config: dict) -> BaseChatModel:
        """
        config is the full model: block from agent_config.yaml.
        Pull out whatever keys the LLM needs.
        """
        return CompanyLLM(
            endpoint=config["endpoint"],
            api_key=config["api_key"],
            model=config.get("model", "company-gpt-v2"),
            temperature=config.get("temperature", 0.1)
        )

    def capabilities(self) -> dict:
        """
        Be honest here — the SDK uses this to catch problems early.
        If tool_calling is False and someone tries to use tools,
        they get a clear error at startup instead of a crash mid-run.
        """
        return {
            "tool_calling": True,    # does this LLM support function calling?
            "streaming": False,      # does it support streaming responses?
            "cost_tracking": False   # add pricing table later in Step 5
        }
```

---

### Step 3 — Register It

One call at the top of `main.py`, before any `AgentRunner.from_config()`:

```python
# main.py

from roscoe.llm import ProviderFactory
from my_project.providers.company_provider import CompanyLLMProvider

# register once — stored in a class-level dict for the process lifetime
ProviderFactory.register("company_llm", CompanyLLMProvider())

# now use it exactly like any built-in provider
from roscoe import AgentRunner
from roscoe.tools import tool

@tool(description="Fetches employee record by ID")
def get_employee(employee_id: str) -> dict:
    return {"id": employee_id, "name": "Priya", "dept": "Engineering"}

agent = AgentRunner.from_config("agent_config.yaml", tools=[get_employee])
result = agent.run("What department does employee E-1042 work in?")
print(result.output)
```

---

### Step 4 — Configure in YAML

The `provider:` value must exactly match the name passed to `register()`:

```yaml
# agent_config.yaml

model:
  provider: company_llm        # matches ProviderFactory.register("company_llm", ...)
  endpoint: ${COMPANY_LLM_URL}
  api_key: ${COMPANY_LLM_KEY}
  model: company-gpt-v2
  temperature: 0.1
  max_tokens: 1000

middleware:
  audit:
    enabled: true
  cost_tracking:
    enabled: true    # shows $0.00 until Step 5
  retry:
    max_attempts: 3
    base_delay_seconds: 1.5
```

---

### Step 5 (Optional) — Add Cost Tracking

If the LLM reports token usage, plug in pricing once and cost appears in
`AgentResult.cost_usd` exactly like the built-in providers:

```python
# main.py — after ProviderFactory.register(), before agent.run()

from roscoe.middleware.cost_tracker import COST_TABLE

COST_TABLE["company_llm"] = {
    "company-gpt-v2":   {"input": 0.002, "output": 0.008},
    "company-gpt-mini": {"input": 0.0005, "output": 0.002},
}
```

---

### Step 6 — Sanity Check

Run this before using in production:

```python
# tests/test_custom_provider.py

from roscoe.llm import ProviderFactory
from my_project.providers.company_provider import CompanyLLMProvider


def test_provider_registered():
    ProviderFactory.register("company_llm", CompanyLLMProvider())
    config = {
        "provider": "company_llm",
        "endpoint": "https://my-company-llm.internal/v1",
        "api_key": "test-key",
        "model": "company-gpt-v2"
    }
    llm = ProviderFactory.get_llm(config)
    assert llm is not None


def test_capabilities_declared():
    provider = CompanyLLMProvider()
    caps = provider.capabilities()
    assert "tool_calling" in caps
    assert "streaming" in caps


def test_end_to_end():
    from roscoe import AgentRunner
    from roscoe.tools import tool

    ProviderFactory.register("company_llm", CompanyLLMProvider())

    @tool(description="Returns hello world")
    def ping(name: str) -> str:
        return f"Hello {name}"

    agent = AgentRunner.from_config("agent_config.yaml", tools=[ping])
    result = agent.run("Say hello to Rhea")

    assert result.error is None
    assert result.output != ""
    assert result.run_id is not None
```

---

### What the SDK Does Automatically After Registration

The custom provider gets all middleware for free — nothing extra to configure:

| Middleware | Behaviour |
|---|---|
| Retry | Retries on `ConnectionError` and `TimeoutError` by default |
| Cost tracker | Records token counts; cost shows `$0.00` until Step 5 is done |
| Audit logger | Logs normally — `provider: company_llm` appears in audit JSON |
| Rate limiter | Enabled if configured in YAML; skipped if not |
| Capability check | Warns at startup if agent needs tool calling but provider declared `false` |

---

### Full Flow Summary

```
their LLM API
      ↓
Step 1: CompanyLLM(BaseChatModel)            ← LangChain wrapper (skip if one exists)
      ↓
Step 2: CompanyLLMProvider(BaseProvider)     ← implement get_llm() + capabilities()
      ↓
Step 3: ProviderFactory.register(name, ...)  ← one call at startup
      ↓
Step 4: provider: company_llm in YAML        ← identical to any built-in provider
      ↓
Step 5: COST_TABLE["company_llm"] = {...}    ← optional, adds cost_usd to AgentResult
      ↓
AgentRunner + all middleware                 ← retry, audit, rate limiting all automatic
```

**Total code written: ~40–60 lines** — just the wrapper and provider class.
Everything else is automatic.

---

## Middleware

All middleware runs automatically on every `agent.run()`. Zero extra code required.
Override any piece per-agent via config.

### Retry

```yaml
middleware:
  retry:
    max_attempts: 3
    base_delay_seconds: 1.5
    jitter: true    # prevents retry storms under high concurrency
```

Catches provider-specific rate limit errors. Reads Azure's `Retry-After` header.
Adds random jitter so retrying agents don't all hit the API simultaneously.

Error types caught per provider:

| Provider | Retriable errors |
|---|---|
| Azure OpenAI | RateLimitError, ServiceUnavailableError (reads Retry-After header) |
| OpenAI | RateLimitError, APIConnectionError |
| Gemini | ResourceExhausted, ServiceUnavailable |
| Anthropic | RateLimitError, OverloadedError |
| Ollama | ConnectionError, ConnectTimeout |

---

### Cost Tracker

Reads token counts via the provider-agnostic `usage_metadata` on each response
(`UsageMetadataCallbackHandler`, langchain-core 0.3.x) — **not** the OpenAI-only
`get_openai_callback`, which doesn't cover Anthropic/Gemini. Calculates cost from a per-model
pricing table. Writes to `AgentResult.cost_usd`.

> **Streaming caveat:** OpenAI/Azure streaming responses report no usage unless
> `stream_options={"include_usage": true}` is set — the cost tracker sets it automatically when
> streaming is on.

```python
# pricing table (rates per 1K tokens) — best-effort, rates drift; verify before shipping
# (model ids are aliases, e.g. claude-sonnet-4-5; confirm against the provider API)
COST_TABLE = {
    "azure_openai": {
        "gpt-4o":       {"input": 0.005,   "output": 0.015},
        "gpt-4o-mini":  {"input": 0.00015, "output": 0.0006},
    },
    "gemini": {
        "gemini-1.5-pro": {"input": 0.0035, "output": 0.0105},
    },
    "anthropic": {
        "claude-sonnet-4-5": {"input": 0.003, "output": 0.015},
    },
    "ollama": {}    # always $0.00
}
```

---

### Audit Logger

Non-blocking via a **background thread + queue** — not `asyncio.create_task`.
`AgentRunner.run()` pushes the record onto a `queue.Queue` (instant, no event loop required)
and a daemon worker thread drains it to the sink. An `atexit` handler flushes the queue
before the process exits so short-lived CLI/script runs never lose their last log.

> **Why not `asyncio.create_task`?** It needs a running event loop (fails from the sync
> `run()`), and fire-and-forget tasks die when `asyncio.run()` closes the loop or the process
> exits — silently dropping logs. The thread+queue path works identically in sync, async, CLI,
> and server contexts.

Fixed schema so every agent across every project produces the same log format.

```json
{
  "run_id": "f3a91c7e-...",
  "agent_name": "LegalRAGAgent",
  "user_id": "rhea@company.com",
  "provider": "azure_openai",
  "model": "gpt-4o",
  "start_time": "2026-06-19T20:00:00Z",
  "end_time": "2026-06-19T20:00:02Z",
  "total_tokens": 1843,
  "cost_usd": 0.012,
  "nodes_traversed": ["retrieve", "generate", "critique"],
  "status": "success",
  "error": null
}
```

Sink options: `local` (JSON files in `./logs/`), `azure_table`, `postgres`.
Configurable per-agent in YAML.

---

### Rate Limiter

Token bucket algorithm. Enforces requests-per-minute per provider deployment.
Skipped automatically for Ollama (local, no external limits).

```yaml
middleware:
  rate_limiter:
    enabled: true
    requests_per_minute: 60
```

---

## Eval System

Run before every deployment. Catches regressions before they reach production.

### Test Case Format

```json
[
  {
    "id": "test_001",
    "input": "What is the liability cap in clause 4B?",
    "expected_output": "Liability is capped at 2x contract value",
    "expected_tools": ["search_docs", "generate_answer"],
    "source_docs": ["clause_4b.txt"]
  }
]
```

### Four Scorers

| Scorer | What it measures | Returns |
|---|---|---|
| `output_quality` | Is the answer correct and relevant? (LLM-as-judge) | 0.0 – 1.0 |
| `tool_usage` | Did the agent call the right tools in the right order? | 0.0 – 1.0 |
| `hallucination` | Did the answer claim things not in the retrieved docs? | 0.0 – 1.0 |
| `regression` | Did the latest change improve or regress vs the last run? | diff report |

### Running Evals

```python
from roscoe.evals import EvalRunner

runner = EvalRunner(
    agent_config="agent_config.yaml",
    dataset="evals/test_cases.json",
    scorers=["output_quality", "hallucination", "tool_usage"]
)
report = runner.run()
print(report.summary())
```

### Regression Comparison

```python
from roscoe.evals import EvalRunner, compare_runs

run_a = EvalRunner(agent_config="config_v1.yaml", dataset="tests.json").run()
run_b = EvalRunner(agent_config="config_v2.yaml", dataset="tests.json").run()
compare_runs(run_a, run_b)

# output:
#                    v1 (old)    v2 (new)    Δ
# Output quality:    0.74        0.83      +0.09  ✅
# Hallucination:     0.12        0.07      -0.05  ✅
# Avg cost:          $0.018      $0.012    -33%   ✅
```

---

## Build Phases

Each phase = one self-contained component. Complete and test each phase fully before
moving to the next. Phases are ordered by dependency — each one builds on the previous.

---

### Phase 0 — Repo Setup

**Component:** Project foundation — everything else depends on this existing first.

- [ ] Create GitHub repo + clone + `poetry init`
- [ ] Create all folders + empty `__init__.py` files
- [ ] `pyproject.toml` — `name = "roscoe"`, `license = "MIT"`,
  `authors = ["rhealaloo <rhealaloo@gmail.com>"]`, repo/homepage
  `https://github.com/rhealaloo45/roscoe`; deps per the pinning rule (langchain/langgraph exact, adapters float)
- [ ] `LICENSE` — MIT, `Copyright (c) 2026 rhealaloo`
- [ ] GitHub Actions CI (pytest on every push to main and dev)
- [ ] `.gitignore` — exclude `.env`, `logs/`, `__pycache__/`
- [ ] Verify `pip install -e .` works
- [ ] Smoke test: `from roscoe import AgentRunner` passes

**Done when:** `pip install -e .` works locally. CI is green. Folder structure exists.
The smoke test fails (AgentRunner not built yet) — that failure is correct and expected.

---

### Phase 1 — Core SDK

**Component:** The central objects every other component depends on —
config loader, tool decorator, state schema, base agent class, and the main entry point.

- [ ] `config/loader.py` — YAML loader with `${ENV_VAR}` resolution
- [ ] Unit tests: env var substitution, missing var raises clear error
- [ ] `tools/decorator.py` — `@tool` wraps `langchain_core.tools.StructuredTool.from_function`
  (adds `description=` ergonomics); reuse LangChain's Pydantic schema inference, don't hand-roll it
- [ ] Unit tests: decorated function has correct name, description, schema, runs correctly
- [ ] `core/agent_result.py` — AgentResult dataclass (output, run_id, tokens, cost, error, `status`, `pending_action`)
- [ ] `core/state.py` — AgentState TypedDict (base state schema for LangGraph)
- [ ] `core/agent_base.py` — AgentBase abstract class with `build_graph()` and lifecycle hooks
- [ ] `core/agent_runner.py` — async-first: `arun()` is the real entry point, `run()` is a thin
  `asyncio.run(arun())` wrapper. `from_config()` reads YAML, builds agent, exposes both.

**Depends on:** Phase 0

**Done when:** `AgentRunner.from_config("config.yaml", tools=[...]).run("...")` returns a
real `AgentResult` with output and token count. One provider (Azure OpenAI) working.

---

### Phase 2 — Provider Factory

**Component:** The abstraction layer that makes the SDK provider-agnostic.
After this phase, swapping from Azure to Gemini to Ollama is a single YAML change —
and users can plug in any LangChain-compatible LLM as a custom provider.

- [ ] `llm/base_provider.py` — `BaseProvider` abstract class with `get_llm()` and `capabilities()`
- [ ] `llm/provider_factory.py` — `ProviderFactory.get_llm(config)` returns a `BaseChatModel`
- [ ] `ProviderFactory.register(name, provider)` — class method for custom provider registration
- [ ] Internal registry dict — checked before built-ins so custom providers always take priority
- [ ] Azure OpenAI built-in (formalise what was built in Phase 1)
- [ ] OpenAI direct built-in
- [ ] Gemini built-in
- [ ] Anthropic built-in
- [ ] Ollama built-in + clear fatal error messages (model not found → `ollama pull`, connection refused → `ollama serve`)
- [ ] `llm/capability_map.py` — per-provider flags for tool calling, streaming, json mode
- [ ] Error message on unknown provider lists built-ins AND hints at `ProviderFactory.register()`
- [ ] Unit tests: each built-in provider instantiates correctly
- [ ] Unit tests: custom provider registered via `register()` is resolved correctly
- [ ] Integration test: change `provider:` in YAML, same agent + tools run unchanged

**Depends on:** Phase 1

**Done when:** All 5 built-in providers work. A user can implement `BaseProvider`,
call `ProviderFactory.register()` once, and use their provider via YAML.

---

### Phase 3 — Middleware

**Component:** The production safety layer — wraps every agent run automatically
without the developer needing to write any of it.

- [ ] `middleware/retry.py` — async retry with exponential backoff + jitter, provider-aware error types
- [ ] `middleware/cost_tracker.py` — LangChain callback hook, per-model pricing table, writes to AgentResult
- [ ] `middleware/audit_logger.py` — non-blocking write via background thread + `queue.Queue`, `atexit` flush, structured JSON schema
- [ ] `middleware/rate_limiter.py` — token bucket algorithm, auto-skips for Ollama
- [ ] Wire all middleware layers into `AgentRunner.run()`
- [ ] Unit tests: retry fires on correct error types, skips on fatal errors
- [ ] Unit tests: cost calculated correctly per provider + model
- [ ] Unit tests: audit JSON has all required fields
- [ ] Integration test: force a 429 → agent retries silently and succeeds
- [ ] Integration test: `result.cost_usd` is populated, audit JSON written to `./logs/`

**Depends on:** Phase 2 (middleware is provider-aware — needs the provider map)

**Done when:** Every `agent.run()` automatically gets retry, cost tracking, audit logging,
and rate limiting with zero extra code from the developer.

---

### Phase 4 — Memory Framework

**Component:** Gives agents the ability to remember — within a session, across sessions,
and from a structured knowledge base. Three distinct memory types, each independently usable.

**Conversation Memory** — remembers what was said earlier in the current session:

- [ ] `memory/conversation.py` — wraps LangChain's `ConversationBufferMemory`
- [ ] Injects conversation history into agent state automatically
- [ ] Configurable window size (last N messages) to control token usage
- [ ] Unit test: second question in same session correctly references first answer

**Persistent Memory** — remembers facts across sessions, stored in a database:

- [ ] `memory/persistent.py` — stores and retrieves key-value facts per `user_id`
- [ ] Backends: SQLite (dev), Postgres (prod), Azure Table Storage (enterprise)
- [ ] Auto-loads relevant facts into agent context at start of every run
- [ ] Unit test: fact stored in run 1 is retrieved in run 2 for same user

**Knowledge Memory** — RAG-style memory from a structured document store:

- [ ] `memory/knowledge.py` — retriever wrapper that pulls relevant docs into context
- [ ] Supports Azure AI Search, FAISS (local), Chroma (local)
- [ ] Configurable `top_k` and similarity threshold
- [ ] Unit test: query returns docs with similarity score above threshold

**Config:**

```yaml
memory:
  conversation:
    enabled: true
    window_size: 10        # last 10 messages
  persistent:
    enabled: true
    backend: sqlite        # sqlite | postgres | azure_table
    connection: ${DB_URL}
  knowledge:
    enabled: true
    type: azure_ai_search
    index: company-knowledge-base
    top_k: 3
```

**Depends on:** Phase 1

**Done when:** An agent using all three memory types correctly recalls conversation history,
retrieves user-specific facts, and pulls relevant knowledge docs — all from config alone.

---

### Phase 5 — Tool Connector Framework

**Component:** Pre-built, ready-to-import `@tool` collections for the enterprise systems
agents most commonly need to interact with. Developers import the tools they need and
pass them to `AgentRunner` — no API integration code required.

**v0.1.0 ships 8 connectors:** REST, Jira, ServiceNow, Outlook, SharePoint, GitHub, Notion,
Snowflake. Seven are HTTP-based (httpx) on a shared `BaseConnector`; Outlook + SharePoint share
a Microsoft Graph OAuth2 base (`_graph_base.py`). Snowflake is SQL (driver, not HTTP) and uses an
**optional dependency**. Confluence and SAP remain deferred (SAP has no single API — OData/BAPI/RFC
per module). The generic REST connector covers most "just call our internal API" cases.

- [x] `connectors/base_connector.py` — `BaseConnector` (httpx client + auth, `transport`-injectable for tests)
- [x] `connectors/rest_api.py` — generic GET/POST/PUT/DELETE (bearer / api_key / basic auth)
- [x] `connectors/jira.py` — create_issue, update_issue, get_issue, search_issues, add_comment (REST v3, ADF)
- [x] `connectors/servicenow.py` — create_ticket, update_ticket, get_ticket_status, search_kb (Table API)
- [x] `connectors/_graph_base.py` — shared MS Graph client-credentials token (cache + bearer injection)
- [x] `connectors/outlook.py` — send_email, read_emails, create_calendar_event, get_availability
- [x] `connectors/sharepoint.py` — search_documents, get_document, list_files, upload_file
- [x] `connectors/github.py` — get_issue, create_issue, search_issues, add_comment, get_file, list_repos
- [x] `connectors/notion.py` — search, get_page, create_page, query_database, append_block
- [x] `connectors/snowflake.py` — run_query, list_tables, describe_table (optional `roscoe[snowflake]` driver)
- [ ] ~~`connectors/confluence.py`~~ — **deferred to v0.2.0**
- [ ] ~~`connectors/sap.py`~~ — **deferred** (no single API; OData/BAPI/RFC per module)
- [x] Each connector reads auth config from YAML (API key, OAuth token, or basic auth)
- [x] Unit tests: each connector tool returns correct schema without hitting real API (mocked via `httpx.MockTransport`; Snowflake via injected connection)
- [ ] Integration test: at least one connector (Jira or ServiceNow) runs against a sandbox

**Usage (class-based — a connector is configured once, then yields its tools):**

```python
from roscoe.connectors import JiraConnector, OutlookConnector
from roscoe import AgentRunner

jira = JiraConnector(config["connectors"]["jira"])
outlook = OutlookConnector(config["connectors"]["outlook"])

agent = AgentRunner.from_config("agent_config.yaml", tools=[*jira.tools, *outlook.tools])
result = agent.run("Find all open P1 bugs and email the team a summary")
```

> **Design note:** connectors are class-based (`Connector(config).tools`) rather than bare
> importable functions — a tool needs its authed client, which the class holds. Cleaner than
> injecting global config into module-level functions.

**Connector config in YAML:**

```yaml
connectors:
  jira:
    base_url: ${JIRA_URL}
    email: ${JIRA_EMAIL}
    api_token: ${JIRA_TOKEN}
  servicenow:
    instance_url: ${SERVICENOW_URL}
    username: ${SERVICENOW_USER}
    password: ${SERVICENOW_PASSWORD}
  outlook:                       # SharePoint uses the same OAuth2 trio + site_id
    client_id: ${OUTLOOK_CLIENT_ID}
    client_secret: ${OUTLOOK_CLIENT_SECRET}
    tenant_id: ${OUTLOOK_TENANT_ID}
    mailbox: ${OUTLOOK_MAILBOX}
  github:
    token: ${GITHUB_TOKEN}
  notion:
    token: ${NOTION_TOKEN}
  snowflake:                     # needs: pip install "roscoe[snowflake]"
    account: ${SNOWFLAKE_ACCOUNT}
    user: ${SNOWFLAKE_USER}
    password: ${SNOWFLAKE_PASSWORD}
    warehouse: ${SNOWFLAKE_WAREHOUSE}
    database: ${SNOWFLAKE_DATABASE}
    schema: ${SNOWFLAKE_SCHEMA}
```

**Depends on:** Phase 1 (connectors use the `@tool` decorator)

**Done when:** A developer can import any connector's tools, add them to `AgentRunner`,
and the agent can interact with that system with zero integration code.

---

### Phase 6 — Human Approval Workflows

**Component:** Lets agents pause before critical or irreversible actions and wait for a
human to approve, reject, or modify before continuing. Essential for enterprise agents that
write to production systems.

**Model: durable suspend + resume — NOT a blocking call.** When an intercepted tool fires,
the graph calls LangGraph `interrupt()`. The run state is persisted to a **checkpointer**
(SQLite dev / Postgres prod) and `run()` returns immediately with
`AgentResult(status="paused", run_id, pending_action)`. A separate `resume()` call continues
the graph from the checkpoint. No thread is held while a human thinks — works in a web request,
a queue worker, or a CLI.

> **Why not block inside `run()`?** A `run()` that blocks up to `timeout_minutes` holds a
> thread/connection for the whole wait — unusable under load. And an outbound Slack *webhook*
> can only *post* a message; it cannot *receive* a button click. Interactive approval needs an
> inbound HTTP endpoint. So we suspend durably and resume via an explicit call.

- [ ] `middleware/human_approval.py` — `ApprovalGate` that wraps tool nodes and calls LangGraph `interrupt()`
- [ ] LangGraph **checkpointer** wired into the compiled graph (SQLite dev / Postgres prod) so paused runs survive process restarts
- [ ] `AgentRunner.resume(run_id, decision, payload=None)` — `decision` ∈ approve | reject | modify; continues from checkpoint
- [ ] Approval record stores: action description, payload, requester, timestamp, **expiry**
- [ ] Notifiers (outbound only): local queue (dev), email (SMTP), Slack webhook post
- [ ] Expiry sweeper job — auto-rejects paused runs past expiry (no long-lived timer)
- [ ] `AgentRunner` config flag: `require_approval_for: ["create_ticket", "send_email"]` (tool names)
- [ ] Auto-intercepts configured tools before execution — developer doesn't change tool code
- [ ] **Optional** `roscoe.approval.receiver` — FastAPI app exposing `/slack/actions` that
  validates Slack signatures and calls `resume()`. Shipped as a separate, opt-in component
  (the only path that makes Slack buttons actually work).
- [ ] CLI fallback for dev/no-server: `roscoe approve <run_id>` / `roscoe reject <run_id>`
- [ ] Unit test: intercepted tool produces a `paused` result with correct `pending_action`
- [ ] Unit test: `resume(..., "approve")` runs the tool; `resume(..., "reject")` stops cleanly
- [ ] Unit test: expiry sweeper marks an old paused run rejected
- [ ] Integration test: Slack notify sent → receiver `/slack/actions` → `resume()` → tool executes

**Usage — developer side (no tool code change needed for auto-intercept):**

```yaml
# agent_config.yaml
middleware:
  human_approval:
    enabled: true
    require_approval_for:
      - create_ticket      # intercept these tool names
      - send_email
      - submit_leave_request
    notify: slack          # slack | email | local
    slack_webhook: ${SLACK_APPROVAL_WEBHOOK}   # outbound notification only
    checkpointer: sqlite   # sqlite | postgres — where paused runs are stored
    expiry_minutes: 30     # sweeper auto-rejects after this
```

```python
# suspend → resume flow
result = agent.run("File a P1 ticket for the outage")
if result.status == "paused":
    # ... human approves out of band (Slack receiver or `roscoe approve`) ...
    result = agent.resume(result.run_id, decision="approve")
print(result.output)
```

**What the approver sees in Slack** (buttons require the optional receiver service; webhook-only
degrades to "reply/▶ approve via CLI"):

```
🔔 Agent Approval Required   (run_id: f3a91c7e)
Agent: IT Support Agent
Action: create_ticket
Payload: {"priority": "P1", "summary": "Checkout API down"}
Requested by: rhea@company.com

[✅ Approve]  [❌ Reject]  [✏️ Modify]
```

**Depends on:** Phase 3 (intercept runs as middleware) + a LangGraph checkpointer

**Done when:** An intercepted tool returns `status="paused"` with durable state; `resume()`
continues approve/modify or stops on reject; expired runs auto-reject; the optional receiver
turns a real Slack click into a `resume()` call.

---

### Phase 7 — Monitoring

**Component:** Visibility into agent health and cost at the fleet level — beyond the
per-run audit log. Dashboards, trend metrics, and alerting across all agent runs.

**Architecture: aggregation is the product; export is optional.** The core reads audit JSON
logs and computes metrics offline — deterministic, no network, fully CI-testable. Exporters are
thin adapters on top, each chosen to fit how an *SDK* runs (mostly short-lived processes, not a
resident server).

- [ ] `monitoring/metrics.py` — aggregates audit logs into time-series metrics (pure, offline):
  - cost per day / per agent / per user
  - p50/p95/p99 latency per agent
  - error rate and error type breakdown
  - token usage trends
- [ ] `monitoring/alerts.py` — threshold rules evaluated over the aggregated metrics: cost/day >
  `$X`, error rate > `Y%`, latency p95 > `Zms` → fire a notifier (reuse Phase 6 Slack/email)
- [ ] `monitoring/exporters/prometheus.py` — **Pushgateway** push for short-lived runs (default);
  `/metrics` scrape endpoint only under the optional `roscoe serve` (no resident server forced)
- [ ] `monitoring/exporters/azure_monitor.py` — push via `azure-monitor-opentelemetry` exporter
- [ ] CLI command: `roscoe monitor` — terminal dashboard reading **local audit logs** (no deps)
- [ ] Unit tests: metric aggregation produces correct totals from mock audit logs (deterministic)
- [ ] Unit test: each exporter is called with the correct payload using a **mocked** client
- [ ] Unit test: alert rule fires/does-not-fire at the configured threshold boundary

> **Dropped:** "metrics appear in Azure Monitor portal within 60s." Ingestion latency is minutes
> and portal state is not a CI-testable assertion. We test the exporter *call*, not the vendor UI.

**Config:**

```yaml
monitoring:
  enabled: true
  exporter: prometheus_pushgateway   # none | prometheus_pushgateway | prometheus_serve | azure_monitor
  prometheus:
    pushgateway_url: ${PUSHGATEWAY_URL}
  azure_monitor:
    connection_string: ${AZURE_MONITOR_CONNECTION}
  alerts:
    daily_cost_usd: 50.00      # alert if daily spend exceeds $50
    error_rate_pct: 5.0        # alert if error rate exceeds 5%
    latency_p95_ms: 5000       # alert if p95 latency exceeds 5s
    notify: slack              # reuse the Phase 6 notifier
```

**Depends on:** Phase 3 (reads from audit logs produced by the audit logger)

**Done when:** `roscoe monitor` shows cost, latency, and error rate from local logs; an alert
fires when a threshold is breached; each exporter is verified by a mocked-client unit test.

---

### Phase 8 — Evals

**Component:** The quality assurance system — automated testing of agent outputs
before every deployment. Catches regressions before they reach production.

- [ ] `evals/dataset.py` — loads `test_cases.json`, validates required fields
- [ ] `evals/scorers/output_quality.py` — LLM-as-judge scorer (uses roscoe itself internally)
- [ ] `evals/scorers/hallucination.py` — checks every claim in the answer against retrieved source docs
- [ ] `evals/scorers/tool_usage.py` — compares actual tool call sequence vs expected sequence
- [ ] `evals/scorers/regression.py` — diffs two EvalRunner runs, shows what improved or regressed
- [ ] `evals/eval_runner.py` — orchestrates all scorers, stores each run with timestamp + run ID
- [ ] `evals/report.py` — per-test breakdown + overall scores + pass/fail verdict
- [ ] Unit tests: each scorer returns a float between 0.0 and 1.0 — `output_quality` and
  `hallucination` are LLM calls, so their **unit** tests use a mocked LLM (no LLM on CI); the
  real check is the integration test
- [ ] Integration test: `EvalRunner.run()` on 5 test cases produces a valid report
- [ ] Integration test: `compare_runs(run_a, run_b)` shows correct diffs

**Depends on:** Phase 3 (EvalRunner uses AgentRunner under the hood, which needs middleware)

**Done when:** `EvalRunner.run()` produces a scored report. `compare_runs()` produces a
diff. Running the same test suite before and after a prompt change shows the delta.

---

### Phase 9 — Agent Templates

**Component:** Pre-built, production-ready agent configurations for the most common
enterprise use cases. A developer picks a template, fills in their credentials, and has
a working agent in minutes — not days.

Each template bundles: `agent_config.yaml` + domain-specific tools + system prompt.

**HR Agent:**

- [ ] `templates/hr_agent/tools/hr_tools.py` — get_leave_balance, submit_leave_request,
  get_policy_document, get_payslip, update_personal_details (uses **REST connector** against the
  HR system + **knowledge memory** for policy docs; SAP/SharePoint swap in at v0.2.0)
- [ ] `templates/hr_agent/prompts/system.txt` — HR assistant persona, policy-grounded, citation-required
- [ ] `templates/hr_agent/agent_config.yaml` — pre-wired with memory + REST connector + approval gate
- [ ] Test: HR agent answers leave balance query via the REST connector (mocked endpoint)

**IT Support Agent:**

- [ ] `templates/it_support_agent/tools/it_tools.py` — create_ticket, check_ticket_status,
  search_knowledge_base, escalate_ticket (uses **ServiceNow connector** + **knowledge memory**
  for the KB; Confluence swaps in at v0.2.0)
- [ ] `templates/it_support_agent/prompts/system.txt` — IT support persona, escalation rules
- [ ] `templates/it_support_agent/agent_config.yaml`
- [ ] Test: IT agent creates a ServiceNow ticket and returns ticket ID

**Legal Agent:**

- [ ] `templates/legal_agent/tools/legal_tools.py` — search_contracts, extract_clause,
  compare_documents, flag_risk (uses **knowledge memory** — FAISS/Chroma local — for the
  contract store; SharePoint swaps in at v0.2.0)
- [ ] `templates/legal_agent/prompts/system.txt` — legal assistant persona, citation-required, no speculation
- [ ] `templates/legal_agent/agent_config.yaml`
- [ ] Test: Legal agent extracts liability clause and cites source document

**CLI integration:**

```bash
# scaffold from a template instead of blank project
roscoe init my-hr-bot --template hr_agent
roscoe init my-it-bot --template it_support_agent
roscoe init my-legal-bot --template legal_agent
```

**Depends on:** Phases 4, 5, 6 (templates use memory, connectors, and approval workflows)

**Done when:** All three templates scaffold correctly via CLI, connect to their
respective systems, and pass their integration tests.

---

### Phase 10 — CLI

**Component:** The developer experience layer — scaffolds a new agent project in one
command so new users are productive within minutes.

- [ ] `cli/init_command.py` — `roscoe init <project-name>` command using Click
- [ ] `roscoe init <name> --template <template>` — scaffold from a pre-built template
- [ ] Jinja2 template: `agent_config.yaml` with all keys pre-filled with sensible defaults
- [ ] Jinja2 template: `tools/my_tools.py` with a commented example `@tool` function
- [ ] Jinja2 template: `prompts/system.txt` with placeholder system prompt
- [ ] Jinja2 template: `main.py` — 10-line entry point stub
- [ ] Jinja2 template: `evals/test_cases.json` — 2 example test cases
- [ ] Jinja2 template: `.env.example` listing all required env vars
- [ ] `roscoe monitor` — terminal dashboard showing live metrics from audit logs
- [ ] `roscoe eval` — run eval suite from terminal without writing Python
- [ ] Register all CLI entry points in `pyproject.toml` under `[tool.poetry.scripts]`
- [ ] Test: `roscoe init my-test-project` creates correct folder structure
- [ ] Test: `roscoe init my-hr-bot --template hr_agent` matches template structure

**Depends on:** Phases 1, 7, 8, 9 (CLI wraps eval runner, monitor, and templates)

**Done when:** A developer with valid API keys can run `roscoe init my-project`,
fill in credentials, and run `python main.py` within 10 minutes.

---

### Phase 11 — Packaging + Launch

**Component:** Making the SDK publicly available and usable by anyone —
PyPI publish, working examples, documentation, and open-source launch.

**Examples (3 real, fully working agents):**
- [ ] `examples/hr_policy_agent/` — HR template, REST connector + knowledge memory + persistent memory
- [ ] `examples/legal_rag_agent/` — Legal template, citation grounding, knowledge memory
- [ ] `examples/it_support_agent/` — IT template, ServiceNow connector, approval workflow

**Pre-publish checklist (gate the push):**
- [ ] **Employer sign-off obtained** — built for the office; if work-for-hire, the employer may
  own the code. Get written OK (manager / legal) before any public push. **Blocks publish.**
- [ ] Secret scan — no hardcoded internal URLs / keys in templates, examples, or configs;
  everything reads `${ENV_VAR}`.

**PyPI (public, account `rhealaloo`):**
- [ ] `poetry build` — produces `dist/` with wheel and sdist
- [ ] `poetry config pypi-token.pypi <token>` — auth as `__token__` with a PyPI API token
- [ ] `poetry publish` — live on public PyPI as `roscoe`
- [ ] Verify `pip install roscoe` works in a clean virtual environment
- [ ] Verify all three examples run after a fresh `pip install roscoe`

**Documentation (MkDocs Material):**
- [ ] Quickstart guide (zero to running agent in 10 minutes)
- [ ] Config reference (every YAML key, type, default, and description)
- [ ] Provider setup guide (auth steps for all 5 built-in providers + custom provider guide)
- [ ] Memory guide (when to use each memory type)
- [ ] Connectors guide (setup and auth for each connector)
- [ ] Human Approval Workflows guide (Slack + email setup)
- [ ] Monitoring guide (Azure Monitor + Prometheus setup)
- [ ] Evals guide (test cases, scorers, regression workflow)
- [ ] Templates guide (which template to pick, how to customise)
- [ ] API reference (auto-generated from docstrings via `mkdocstrings`)

**Launch:**
- [ ] `CHANGELOG.md` — document everything built in Phases 0–10
- [ ] GitHub release: tag `v0.1.0`, attach wheel
- [ ] README: quickstart, badges (PyPI version, CI status, MIT license)
- [ ] Medium post: "I built a production-grade LangChain agent framework from scratch"
- [ ] LinkedIn + HN post

**Depends on:** All previous phases

**Done when:** `pip install roscoe` works. Docs are live. GitHub release is tagged.
Anyone can go from install to running agent in under 10 minutes.

---

## 3-Day Quick Start

The foundation everything else builds on. Do these 3 days in order before anything else.

### Day 1 — Foundation (~1h 50m)

| # | Task | File | Time |
|---|---|---|---|
| 1 | Create GitHub repo + clone + `poetry init` | — | 20m |
| 2 | Create all folders + empty `__init__.py` files | all dirs | 15m |
| 3 | `pyproject.toml` with all deps pinned | `pyproject.toml` | 25m |
| 4 | GitHub Actions CI (pytest on push) | `.github/workflows/ci.yml` | 20m |
| 5 | Verify `pip install -e .` works | — | 10m |
| 6 | Smoke test: `from roscoe import AgentRunner` passes | `tests/test_smoke.py` | 20m |

**EOD:** `pip install -e .` works. CI is green. Structure exists. Nothing runs yet — correct.

---

### Day 2 — Core Logic (~2h 25m)

| # | Task | File | Time |
|---|---|---|---|
| 1 | YAML config loader with env var resolution | `config/loader.py` | 35m |
| 2 | Unit tests for config loader | `tests/unit/test_config.py` | 20m |
| 3 | `@tool` decorator — fn signature → StructuredTool | `tools/decorator.py` | 40m |
| 4 | Unit tests for `@tool` | `tests/unit/test_tools.py` | 20m |
| 5 | AgentResult dataclass | `core/agent_result.py` | 15m |
| 6 | AgentState TypedDict | `core/state.py` | 15m |

**EOD:** Can load a YAML, decorate a function with `@tool`, get an AgentResult type.
No LLM calls yet — correct.

---

### Day 3 — First Working Agent (~2h 40m)

| # | Task | File | Time |
|---|---|---|---|
| 1 | ProviderFactory — Azure OpenAI only for now | `llm/provider_factory.py` | 25m |
| 2 | AgentBase abstract class with lifecycle hooks | `core/agent_base.py` | 20m |
| 3 | `AgentRunner.from_config()` — main entry point | `core/agent_runner.py` | 40m |
| 4 | Wire default agent executor internally in AgentRunner | `core/agent_runner.py` | 35m |
| 5 | End-to-end test: YAML → run → AgentResult | `tests/integration/test_e2e.py` | 30m |
| 6 | Push, confirm CI passes | — | 10m |

**EOD:** `AgentRunner.from_config().run("...")` returns a real AgentResult with output,
tokens, and run_id. The entire foundation is working.

---

## Production Considerations

### What holds up at scale

- **ProviderFactory** — stateless, zero bottleneck at any scale
- **AgentRunner** — LangGraph compiled graphs are thread-safe
- **Retry logic** — fine at scale as long as it stays async (it does)

### What to watch at scale

| Issue | Symptom | Fix |
|---|---|---|
| Audit log blocking responses | Response latency spikes | Background thread + queue + `atexit` flush (already done) |
| Retry storm on 429 | Mass failures compound each other | Jitter on backoff (already done) |
| LangChain version bump | Silent behaviour change | Pin all deps + run evals before any upgrade |
| Large LangGraph state | Memory climb, slow serialisation | Store doc IDs in state, not full text |
| 1000 concurrent agents | Azure rate limits thrashed | Semaphore concurrency cap in AgentRunner |

### Scale thresholds

| Daily requests | Status | What's needed |
|---|---|---|
| < 1,000 | ✅ Works as-is | Nothing extra |
| 1,000 – 10,000 | ⚠️ Monitor | Thread-queue audit (done), concurrency limit |
| 10,000 – 100,000 | ⚠️ Needs work | Message queue for audit, cost reconciliation job |
| 100,000+ | ❌ Rearchitect | Move off LangChain to a leaner custom orchestrator |

---

## Future Additions (Post v0.1.0)

### Blueprint System

Pre-wired LangGraph graph topologies so developers don't need to wire their own graphs.
Planned topologies: ReAct, RAGCritic, PlanExecute, Supervisor, HITL.
Developers pick a blueprint in config and only write tools + prompts.

Status: **planned for v0.2.0**

### Additional Connectors

Phase 5 (v0.1.0) ships **8 connectors**: REST, Jira, ServiceNow, Outlook, SharePoint, GitHub,
Notion, Snowflake. Still deferred: **Confluence** and **SAP** (SAP has no single API —
OData/BAPI/RFC per module). Future connectors: Salesforce, Workday, Slack, Teams, Zendesk.

Status: **community contributions welcome post-launch**

### Rust Hot Path

Extract performance-critical middleware into a Rust crate via PyO3.
Target: rate limiter (token bucket atomics), audit log writer (serde_json),
cost calculator. Expected ~10x throughput improvement on middleware operations.

Status: **planned post v0.2.0**

---

## Key Design Decisions

| Decision | Choice | Why |
|---|---|---|
| Orchestration foundation | LangChain + LangGraph | The AI ecosystem lives here. All provider SDKs, tool abstractions, and agent loops are Python/LangChain. |
| Dep pinning strategy | Pin langchain/langgraph exact; adapters + core float; lockfile pins the rest | Exact-pinning every package deadlocks the resolver (each adapter pins its own core range). Top-level pins + committed `poetry.lock` give stability without the deadlock. |
| Async strategy | Async-first core: `arun()` real, `run()` = `asyncio.run(arun())` | One code path; sync callers get a wrapper. Don't retrofit async later. |
| Audit log path | Background thread + `queue.Queue` + `atexit` flush | Survives sync calls, `asyncio.run()` loop close, and process exit — where `asyncio.create_task` silently drops logs. |
| HITL control flow | LangGraph `interrupt()` + checkpointer, suspend→`resume()` | Blocking `run()` holds a thread for the human's whole wait; a Slack *webhook* can't receive clicks. Durable suspend + explicit resume is the only model that scales and actually wires to Slack (via the optional receiver). |
| Monitoring split | Offline log aggregation (core) + thin exporters (opt-in) | Aggregation is deterministic and CI-testable; an SDK shouldn't force a resident server. Pushgateway for short runs, `/metrics` only under `roscoe serve`. |
| Connector v0.1 scope | 8 shipped (REST, Jira, ServiceNow, Outlook, SharePoint, GitHub, Notion, Snowflake); Confluence/SAP deferred | Class-based (`Connector(config).tools`); Graph auth shared; Snowflake driver optional. SAP's split API isn't worth it for v0.1. |
| Provider abstraction | ProviderFactory + BaseProvider | LangChain's BaseChatModel already unifies all providers. Factory picks the right one from config. BaseProvider lets users extend without forking the SDK. |
| Custom provider pattern | Plugin registry via `register()` | Users implement one interface, call one method. After that their provider is indistinguishable from built-ins — same YAML, same middleware, same evals. |
| Retry scope | Per LLM call, not per graph | Graph-level retry re-runs all nodes. LLM-call retry is surgical and correct. |
| YAML config | Everything describable in YAML | Non-engineers can spin up agent variants. No Python needed for basic use. |
| Test strategy | Unit (no LLM) + integration (real LLM) | Unit tests run on CI always. Integration tests skip without API keys. |

---

## Contribution Guidelines

- One feature per PR
- Every PR needs unit tests
- Integration tests must pass before merge
- Run eval suite before any dependency upgrade
- Changelog entry required for every PR
- Semantic versioning: breaking change = major bump

---

## Links

- Repo: https://github.com/rhealaloo45/roscoe
- PyPI: https://pypi.org/project/roscoe (live after Phase 11)
- Docs: https://rhealaloo45.github.io/roscoe (live after Phase 11)
- Issues: https://github.com/rhealaloo45/roscoe/issues
