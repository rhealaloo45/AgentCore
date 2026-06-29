# ROSCOE — System Overview

**R**eady-to-run **O**rchestration **S**DK — **C**onfigurable, **O**bservable, **E**xtensible

---

## What ROSCOE Is

A Python SDK that lets you build LLM-powered agents with production infrastructure baked in. You write your business logic as plain Python functions and describe your agent in YAML. ROSCOE handles everything else — retries, cost tracking, rate limiting, audit logging, human approval, memory, and monitoring.

**Built on LangChain (models + tools + messages). No LangGraph.** ROSCOE runs its own ReAct loop.

---

## The Stack

```
What ROSCOE uses from LangChain:
─────────────────────────────────
• LLM wrappers     — ChatOpenAI, AzureChatOpenAI, ChatGoogleGenerativeAI, ChatAnthropic, ChatOllama
• Message types    — HumanMessage, AIMessage, SystemMessage, ToolMessage
• Tool abstraction — StructuredTool (wraps a Python function into something the LLM can call)
• Runnable.with_retry — LangChain's retry binding (wraps the model)

What ROSCOE builds itself:
──────────────────────────
• ReAct loop        — executor.py (~100 lines)
• HITL gate         — approval/gate.py (early return from loop)
• All middleware    — retry config, rate limiter, cost tracker, audit logger
• Memory system    — conversation, persistent, knowledge/RAG
• Connectors       — 9 enterprise API integrations
• Monitoring       — metrics aggregation, dashboard, alerts, exporters
• Evals            — dataset, scorers, regression diffing
• CLI              — init (GUI wizard), monitor, eval
```

---

## How It Works: The Full Flow

### Step 1: Configuration Loading

When you call `AgentRunner.from_config("agent_config.yaml", tools=[...])`:

```
agent_config.yaml
       │
       ▼
config/loader.py
  • Reads YAML
  • Resolves ${ENV_VAR} placeholders from os.environ
  • Returns a plain Python dict
       │
       ▼
Dict: {
  "agent_name": "my-agent",
  "model": {"provider": "openai", "model": "gpt-4o-mini", "api_key": "sk-..."},
  "middleware": {"retry": {...}, "rate_limiter": {...}, ...},
  "memory": {"conversation": {...}, "persistent": {...}}
}
```

### Step 2: Provider Resolution

```
config["model"]["provider"] = "openai"
       │
       ▼
ProviderFactory.get_llm(config["model"])
  • Checks custom registry first (ProviderFactory.register() overrides)
  • Falls back to built-in providers
  • Lazy-imports the LangChain adapter (langchain-openai, langchain-anthropic, etc.)
  • Returns a BaseChatModel instance
       │
       ▼
ChatOpenAI(model="gpt-4o-mini", api_key="sk-...", temperature=0.1)
```

Built-in providers and what they instantiate:

| Config `provider:` | LangChain class | Package |
|---|---|---|
| `openai` | `ChatOpenAI` | langchain-openai |
| `azure_openai` | `AzureChatOpenAI` | langchain-openai |
| `anthropic` | `ChatAnthropic` | langchain-anthropic |
| `gemini` | `ChatGoogleGenerativeAI` | langchain-google-genai |
| `ollama` | `ChatOllama` | langchain-ollama |

OpenRouter works via `openai` provider + `base_url: https://openrouter.ai/api/v1`.

### Step 3: Tool Binding + Retry Wrapping

```
ChatOpenAI instance
       │
       ▼
model.bind_tools([tool1, tool2, ...])
  • Tells the LLM what functions it can call
  • LangChain converts each @tool's schema to the LLM's function-calling format
  • Returns a RunnableBinding (model + tools together)
       │
       ▼
apply_retry(model, retry_config, provider)
  • Wraps the model with LangChain's Runnable.with_retry()
  • Configures which exceptions to retry (provider-specific)
  • Sets max_attempts, exponential backoff, jitter
  • Returns a RunnableRetry wrapping the RunnableBinding
       │
       ▼
Final model object: RunnableRetry(RunnableBinding(ChatOpenAI + tools))
```

**Why bind tools BEFORE retry?** If you retry first, the retry wrapper hides `bind_tools()` from the model. The executor needs the model to be tool-aware when it calls `ainvoke()`.

### Step 4: Build the Executor

```
ReactExecutor(
    model=<retry-wrapped, tool-bound model>,
    tools=[tool1, tool2, ...],
    system_prompt="You are an IT support agent...",
    max_iterations=10,
    approval_gate=ApprovalGate(["send_email", "create_ticket"])
)
```

The executor holds:
- The model (for LLM calls)
- A dict of tools keyed by name (for execution)
- The system prompt (prepended to first message)
- The approval gate (decides which tools need human OK)

### Step 5: Build Memory + Rate Limiter

```
Memory (from config):
  • ConversationMemory(window_size=10) — or None if disabled
  • PersistentMemory(backend="sqlite", connection="./facts.db") — or None

Rate Limiter:
  • RateLimiter() configured with requests_per_minute from config
  • Token bucket: starts full, drains on each call, refills over time
```

### Step 6: AgentRunner Instance Created

```python
AgentRunner(
    config=config,
    executor=ReactExecutor(...),
    agent_name="my-agent",
    provider="openai",
    model="gpt-4o-mini",
    middleware={...},
    rate_limiter=RateLimiter(...),
    conversation=ConversationMemory(...),
    persistent=PersistentMemory(...),
    pending_store=PendingStore()     # holds paused HITL runs
)
```

---

## How `agent.run()` Works (The Execution Path)

```python
result = agent.run("Create a P1 ticket for the outage", user_id="john@acme.com", session_id="s1")
```

### 1. Rate Limiter

```python
await self._rate_limiter.acquire(self.provider)
```

Token bucket check. If bucket empty → wait until a token refills. Prevents API hammering.

**How token bucket works:**
- Bucket starts with N tokens (e.g., 60 for 60 RPM)
- Each `acquire()` takes 1 token
- Tokens refill at a rate of N per minute
- If 0 tokens left → `acquire()` awaits until refill

Skipped for Ollama (local, no rate limits).

### 2. Build Input Messages

```python
messages = []

# Persistent memory — facts about this user from previous sessions
if persistent_memory and user_id:
    facts = persistent.all("john@acme.com")
    # e.g., {"department": "Engineering", "open_ticket": "INC001"}
    messages.append(SystemMessage("Known facts: department=Engineering; open_ticket=INC001"))

# Conversation memory — recent messages from this session
if conversation_memory and session_id:
    messages.extend(conversation.get("s1"))
    # e.g., [HumanMessage("hi"), AIMessage("hello!"), ...]

# The new user message
messages.append(HumanMessage("Create a P1 ticket for the outage"))
```

### 3. ReactExecutor Loop

This is the core. ~100 lines in `executor.py`:

```python
async def _loop(self, convo):
    # Prepend system prompt if not already there
    if self._system and not starts_with_system(convo):
        convo.insert(0, SystemMessage(content=self._system))

    for _ in range(self._max_iterations):    # default: 10

        # ─── CALL THE LLM ───
        reply: AIMessage = await self._model.ainvoke(convo)
        convo.append(reply)
        # At this point, retry is automatic — if the LLM returns 429,
        # the RunnableRetry wrapper handles backoff + retry invisibly

        # ─── CHECK FOR TOOL CALLS ───
        tool_calls = reply.tool_calls  # list of {name, args, id}

        if not tool_calls:
            # No tools needed → LLM gave a final answer
            return ExecResult(messages=convo, status="success")

        # ─── HITL GATE ───
        if self._gate and any(self._gate.needs_approval(c["name"]) for c in tool_calls):
            # At least one tool needs human approval
            # STOP HERE — don't execute anything
            return ExecResult(
                messages=convo,
                status="paused",
                pending_tool_calls=tool_calls
            )

        # ─── EXECUTE TOOLS ───
        for call in tool_calls:
            tool = self._tools[call["name"]]
            result = await tool.ainvoke(call["args"])
            convo.append(ToolMessage(content=result, tool_call_id=call["id"]))

        # Loop back → LLM sees tool results, decides what to do next

    # Ran out of iterations without a final answer
    return ExecResult(status="error", error="Max iterations reached")
```

**What the LLM sees at each iteration:**

```
Iteration 1:
  [SystemMessage: "You are IT support..."]
  [SystemMessage: "Known facts: department=Engineering"]
  [HumanMessage: "Create a P1 ticket for the outage"]
  → LLM responds with tool_call: create_ticket(priority="P1", summary="Outage")

Iteration 1 (HITL check):
  "create_ticket" is in require_approval_for → PAUSE
  → Loop stops, returns status="paused"
```

### 4. Paused State (HITL)

When the loop returns `status="paused"`:

```python
# Save the entire conversation + pending tool calls
self._pending.save(PendingRun(
    run_id="abc-123",
    messages=convo,           # full message history up to this point
    tool_calls=[{"name": "create_ticket", "args": {"priority": "P1", ...}}],
    user_id="john@acme.com",
    session_id="s1",
    human_message=human       # the original HumanMessage
))

# Return to caller
return AgentResult(
    status="paused",
    pending_action={"tool_calls": [...]},  # what the agent wants to do
    run_id="abc-123"
)
```

**PendingStore** is an in-memory dict: `{run_id: PendingRun}`. For multi-process deployments, swap in a sqlite/redis-backed store (same interface: `save()`, `get()`, `pop()`).

### 5. Resume (After Human Decision)

```python
result = agent.resume("abc-123", "approve")
```

What happens:

```python
async def aresume(self, run_id, decision, payload=None):
    pending = self._pending.pop(run_id)   # retrieve and remove from store
    convo = pending.messages              # conversation where we left off

    for call in pending.tool_calls:
        if decision == "approve":
            # Execute the tool as-is
            result = await tool.ainvoke(call["args"])
            convo.append(ToolMessage(content=result))

        elif decision == "reject":
            # Tell the LLM it was blocked
            convo.append(ToolMessage("Action 'create_ticket' was rejected by a human."))

        elif decision == "modify":
            # Execute with edited args
            result = await tool.ainvoke(payload)  # payload = new args
            convo.append(ToolMessage(content=result))

    # Resume the loop from where it stopped
    exec_result = await self._executor.resume(convo)
    # → LLM sees tool results, continues reasoning, returns final answer
```

### 6. Cost Tracking

After the loop finishes:

```python
input_tokens, output_tokens, total = sum_usage(exec_result.messages)
```

`sum_usage()` iterates over all AIMessages in the conversation, reads `usage_metadata` from each (LangChain populates this from the provider's response), and sums them.

```python
cost = calculate_cost("openai", "gpt-4o-mini", input_tokens, output_tokens)
```

Looks up the pricing table:

```python
COST_TABLE = {
    "openai": {
        "gpt-4o":      {"input": 0.005,   "output": 0.015},
        "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    },
    "azure_openai": {...},
    "anthropic": {...},
    "gemini": {...},
    "ollama": {}  # always $0.00
}

# Formula: (input_tokens / 1000 * input_rate) + (output_tokens / 1000 * output_rate)
```

### 7. Conversation Memory Update

On success (not error/paused):

```python
if conversation_memory and session_id:
    conversation.add("s1", human_message, AIMessage(content=output))
```

The sliding window trims to the last N messages:

```python
class ConversationMemory:
    def add(self, session_id, *messages):
        history = self._store[session_id]
        history.extend(messages)
        if len(history) > self.window_size:
            self._store[session_id] = history[-self.window_size:]
```

### 8. Audit Log

Non-blocking write via background thread:

```python
self._audit.log({
    "run_id": "abc-123",
    "agent_name": "it-helpdesk",
    "user_id": "john@acme.com",
    "provider": "openai",
    "model": "gpt-4o-mini",
    "start_time": "2026-06-29T14:30:00Z",
    "end_time": "2026-06-29T14:30:02Z",
    "total_tokens": 1843,
    "cost_usd": 0.011,
    "nodes_traversed": ["search_kb", "create_ticket"],
    "status": "success",
    "error": null
})
```

**How the non-blocking logger works:**

```
agent.run() thread              Background worker thread
─────────────────────           ─────────────────────────
audit.log(record)
  │
  ▼
queue.put(record)  ──────→  queue.get()
  │ (instant, non-blocking)      │
  │                              ▼
  │                         json.dumps(record)
  │                         file.write(line + "\n")
  │                         file.flush()
  ▼
continues immediately
(no I/O wait)
```

`atexit` handler ensures the queue is drained before process exit (no lost logs).

### 9. Return AgentResult

```python
AgentResult(
    output="Created ticket INC0012345. Priority: P1. Assigned to Platform Team.",
    run_id="abc-123",
    total_tokens=1843,
    cost_usd=0.011,
    status="success",          # "success" | "error" | "paused"
    error=None,
    tool_calls=["search_kb", "create_ticket"],
    pending_action=None        # populated only when status="paused"
)
```

---

## How Retry Works (In Detail)

Retry is applied **per LLM call**, not per entire run. This is important — if the agent made 3 successful tool calls and the 4th LLM call gets a 429, only that one call retries (not the whole run).

```python
# middleware/retry.py

def apply_retry(model, retry_config, provider):
    """Wrap a model with LangChain's Runnable.with_retry()."""
    max_attempts = retry_config.get("max_attempts", 3)
    base_delay = retry_config.get("base_delay_seconds", 1.5)

    exceptions = retriable_exceptions(provider)
    # e.g., for "openai": (ConnectionError, TimeoutError, RateLimitError, APIConnectionError)

    return model.with_retry(
        retry_if_exception_type=exceptions,
        stop_after_attempt=max_attempts,
        wait_exponential_jitter=True,     # 1.5s → 3s → 6s (with random jitter)
    )
```

**Why jitter?** If 10 agents all get a 429 at the same time and retry after exactly 1.5s, they all hit the API again simultaneously → another 429. Jitter adds randomness so retries spread out:

```
Agent A retries after: 1.5s + random(0, 0.5s) = 1.72s
Agent B retries after: 1.5s + random(0, 0.5s) = 1.91s
Agent C retries after: 1.5s + random(0, 0.5s) = 1.53s
```

---

## How Rate Limiting Works (In Detail)

```python
# middleware/rate_limiter.py

class RateLimiter:
    """Token bucket algorithm."""

    def configure(self, provider, config):
        if provider == "ollama":
            return  # skip — local model, no limits
        self._rpm = config.get("requests_per_minute", 60)
        self._tokens = self._rpm           # bucket starts full
        self._refill_rate = self._rpm / 60  # tokens per second

    async def acquire(self, provider):
        if provider == "ollama":
            return  # no-op

        # Refill tokens based on time elapsed since last refill
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self._rpm, self._tokens + elapsed * self._refill_rate)
        self._last_refill = now

        if self._tokens >= 1:
            self._tokens -= 1
            return  # proceed immediately

        # Bucket empty — wait for next token
        wait_time = (1 - self._tokens) / self._refill_rate
        await asyncio.sleep(wait_time)
        self._tokens = 0
```

**Rate Limiter vs Retry — different problems:**

| | Rate Limiter | Retry |
|---|---|---|
| When | BEFORE the LLM call | AFTER a failed LLM call |
| Purpose | Prevent 429s proactively | Recover from transient failures |
| Mechanism | Throttles outbound requests | Re-sends failed requests |
| Analogy | Traffic light (controls flow) | Spare tire (handles failure) |

---

## How Memory Works (In Detail)

### Conversation Memory

**Problem:** LLMs are stateless. Each call is independent. Without memory, "What about SKU-002?" makes no sense after asking about SKU-001.

**Solution:** Store messages per session, inject them before each new call.

```
Session "chat-001" store:
  [HumanMessage("What's the price of SKU-001?"),
   AIMessage("The price of SKU-001 is $19.99"),
   HumanMessage("What about SKU-002?"),
   AIMessage("The price of SKU-002 is $24.99")]

Window size: 10 → keeps last 10 messages, drops older ones
```

On the next `agent.run(session_id="chat-001")`:
- These messages are prepended to the input
- LLM sees the full context
- Can reference earlier conversation

### Persistent Memory

**Problem:** Conversation memory dies when the session ends. Agent forgets everything about a user across sessions.

**Solution:** Key-value store per user_id in SQLite.

```python
# During a run, if the agent learns something:
persistent.set("john@acme.com", "department", "Engineering")
persistent.set("john@acme.com", "open_ticket", "INC0012345")

# Next session (next day), at the start of run:
facts = persistent.all("john@acme.com")
# → {"department": "Engineering", "open_ticket": "INC0012345"}
# Injected as: SystemMessage("Known facts: department=Engineering; open_ticket=INC0012345")
```

### Knowledge Memory (RAG)

**Problem:** Agent needs to answer from documents (policies, contracts, manuals) it hasn't been trained on.

**Solution:** Vector/keyword search over a document store. Agent calls a retriever tool to pull relevant chunks into context.

```python
from roscoe.memory.knowledge import KnowledgeMemory

km = KnowledgeMemory.from_texts(
    ["Remote work policy: employees may work from home 3 days/week...",
     "Leave policy: 20 days annual leave, carry forward max 5..."],
    metadatas=[{"source": "hr_handbook.pdf"}, {"source": "hr_handbook.pdf"}]
)

# When agent needs to answer "What's the remote work policy?":
results = km.search("remote work policy", top_k=3)
# → Returns top 3 matching chunks with scores
```

Backends:
- **FAISS** — fast vector search (if `faiss-cpu` installed)
- **Keyword** — zero-dependency fallback (TF-IDF-style)

---

## How Connectors Work (In Detail)

Each connector is a class that:
1. Takes auth config in its constructor
2. Creates an authenticated httpx client
3. Exposes a `.tools` list of LangChain StructuredTools

```python
class JiraConnector(BaseConnector):
    def __init__(self, config):
        # Build authenticated httpx client
        self._client = httpx.AsyncClient(
            base_url=config["base_url"],
            headers={"Authorization": f"Basic {b64(email:token)}"}
        )

    @property
    def tools(self) -> list[StructuredTool]:
        return [
            StructuredTool.from_function(self.create_issue, ...),
            StructuredTool.from_function(self.search_issues, ...),
            StructuredTool.from_function(self.get_issue, ...),
            StructuredTool.from_function(self.add_comment, ...),
        ]

    async def create_issue(self, project: str, summary: str, priority: str) -> str:
        resp = await self._client.post("/rest/api/3/issue", json={...})
        return f"Created {resp.json()['key']}"
```

Usage:

```python
from roscoe.connectors import JiraConnector, ServiceNowConnector

jira = JiraConnector(config["connectors"]["jira"])
snow = ServiceNowConnector(config["connectors"]["servicenow"])

agent = AgentRunner.from_config("config.yaml", tools=[*jira.tools, *snow.tools, my_custom_tool])
```

The LLM sees these tools the same as any `@tool` function — it doesn't know or care whether it's calling your code or a Jira API wrapper.

---

## How the @tool Decorator Works

```python
from roscoe.tools import tool

@tool
def get_price(sku: str) -> dict:
    """Fetch the price for a product SKU."""
    return {"sku": sku, "price": 1999}
```

Under the hood:

```
@tool decorator
       │
       ▼
LangChain's StructuredTool.from_function(
    func=get_price,
    name="get_price",                    # from function name
    description="Fetch the price...",     # from docstring
    args_schema=<auto-generated Pydantic model from type hints>
)
       │
       ▼
What the LLM receives (in OpenAI function-calling format):
{
    "name": "get_price",
    "description": "Fetch the price for a product SKU.",
    "parameters": {
        "type": "object",
        "properties": {
            "sku": {"type": "string"}
        },
        "required": ["sku"]
    }
}
```

The LLM reads the description to decide when to call it, and the schema to know what arguments to pass.

---

## How Monitoring Works

```
agent.run() writes audit JSONL (automatically)
       │
       ▼
./logs/audit.jsonl grows over time
(one line per run — run_id, agent, cost, tokens, latency, status, errors)
       │
       ▼
roscoe monitor --path logs/audit.jsonl
       │
       ▼
monitoring/metrics.py: aggregate(load_audit())
  • Parses all JSONL lines
  • Groups by agent, by status, by error type
  • Calculates: total cost, cost/agent, latency percentiles, error rates
       │
       ▼
monitoring/dashboard.py: render(metrics)
  • Formats Metrics as plain text
  • Prints to terminal
       │
       ▼
Terminal output:
  runs: 847   error rate: 2.1%   total cost: $14.23
  ...
```

**Alerts** layer on top:

```python
# monitoring/alerts.py
if metrics.total_cost_usd > alert_config["daily_cost_usd"]:
    notifier.send("Cost alert: $14.23 exceeds $10/day threshold")
```

Notifiers: Slack webhook or email (SMTP).

**Exporters** push metrics to external systems:
- `prometheus.py` → Pushgateway (for Grafana dashboards)
- `azure_monitor.py` → Azure Monitor (OpenTelemetry)

---

## How Evals Work

```
test_cases.json
       │
       ▼
EvalRunner(agent, scorers=[tool_usage, output_quality, hallucination])
       │
       ▼
For each case:
  1. agent.run(case.input)         → get actual output + tool_calls
  2. tool_usage.score(expected_tools vs actual tool_calls)    → 0.0–1.0
  3. output_quality.score(expected_output vs actual output)   → 0.0–1.0 (LLM judge)
  4. hallucination.score(output vs context_docs)              → 0.0–1.0 (LLM judge)
       │
       ▼
EvalReport:
  • Per-case scores
  • Overall mean per scorer
  • Pass/fail verdict (mean >= threshold)
       │
       ▼
Regression diffing:
  compare_runs(report_v1, report_v2) → which cases improved, which regressed
```

---

## How the CLI Works

### `roscoe init my-agent`

```
roscoe init my-agent
       │
       ├── --quick flag? → skip wizard, use defaults
       ├── --cli flag?   → terminal wizard (prompts in terminal)
       └── default       → GUI wizard (Tkinter window)
              │
              ▼
       Wizard collects:
         • Provider (OpenAI / Azure / Anthropic / Gemini / Ollama / OpenRouter)
         • Model name
         • Middleware toggles (retry, rate limit, cost, audit, HITL)
         • Memory toggles (conversation, persistent)
              │
              ▼
       Scaffold project:
         my-agent/
         ├── agent_config.yaml    ← filled with wizard answers, heavily commented
         ├── main.py              ← 6-line entry point
         ├── tools/my_tools.py    ← example @tool with explanation
         ├── prompts/system.txt   ← placeholder persona
         ├── evals/test_cases.json
         ├── docs.md              ← 16-section developer guide
         └── .env.example         ← all credential placeholders
```

### `roscoe init my-agent --template hr_agent`

Copies the template directory (pre-built tools + prompt + config) instead of the blank scaffold. Adds the project-level files the template doesn't carry (main.py, .env.example, etc.).

---

## File Map

```
roscoe/
├── __init__.py                         ← exports AgentRunner, __version__
├── core/
│   ├── agent_runner.py                 ← AgentRunner: from_config(), run(), resume()
│   ├── executor.py                     ← ReactExecutor: the ReAct loop (~100 lines)
│   ├── agent_result.py                 ← AgentResult dataclass
│   ├── agent_base.py                   ← abstract base (legacy, not actively used)
│   └── state.py                        ← AgentState TypedDict
├── approval/
│   └── gate.py                         ← ApprovalGate + PendingRun + PendingStore
├── config/
│   └── loader.py                       ← YAML loading + ${ENV_VAR} resolution
├── tools/
│   └── decorator.py                    ← @tool decorator
├── llm/
│   ├── provider_factory.py             ← ProviderFactory: get_llm(), register(), capabilities()
│   ├── base_provider.py                ← BaseProvider interface (for custom providers)
│   └── capability_map.py               ← per-provider feature flags
├── middleware/
│   ├── retry.py                        ← apply_retry() + retriable_exceptions()
│   ├── cost_tracker.py                 ← COST_TABLE + calculate_cost() + sum_usage()
│   ├── audit_logger.py                 ← background thread + queue JSONL writer
│   └── rate_limiter.py                 ← token bucket RateLimiter
├── memory/
│   ├── conversation.py                 ← per-session sliding window
│   ├── persistent.py                   ← per-user key-value (SQLite)
│   └── knowledge.py                    ← RAG retriever (FAISS / keyword)
├── connectors/
│   ├── base_connector.py               ← BaseConnector (httpx + auth)
│   ├── _graph_base.py                  ← shared MS Graph OAuth2 (Outlook + SharePoint)
│   ├── rest_api.py                     ← generic REST (any API)
│   ├── jira.py                         ← Jira Cloud REST v3
│   ├── servicenow.py                   ← ServiceNow Table API
│   ├── outlook.py                      ← MS Graph mail/calendar
│   ├── sharepoint.py                   ← MS Graph documents
│   ├── github.py                       ← GitHub REST API
│   ├── notion.py                       ← Notion API
│   ├── google_workspace.py             ← Gmail, Calendar, Tasks, Drive
│   └── snowflake.py                    ← SQL queries (optional driver)
├── monitoring/
│   ├── metrics.py                      ← aggregate audit logs → Metrics dataclass
│   ├── dashboard.py                    ← render Metrics → terminal text
│   ├── alerts.py                       ← threshold rules → fire notifier
│   ├── notifier.py                     ← Slack webhook + email (SMTP)
│   └── exporters/
│       ├── prometheus.py               ← Pushgateway push
│       └── azure_monitor.py            ← OpenTelemetry push
├── evals/
│   ├── dataset.py                      ← loads + validates test_cases.json
│   ├── eval_runner.py                  ← EvalRunner: orchestrates scorers
│   ├── report.py                       ← EvalReport formatting
│   ├── regression.py                   ← compare_runs() for diffing
│   └── scorers/
│       ├── base.py                     ← Scorer interface + ScoreResult
│       ├── tool_usage.py               ← deterministic tool sequence check
│       ├── output_quality.py           ← LLM-as-judge quality (0–10)
│       └── hallucination.py            ← LLM-as-judge claims vs docs
├── templates/
│   ├── hr_agent/                       ← HR template (tools + prompt + config)
│   ├── it_support_agent/               ← IT Support template
│   ├── legal_agent/                    ← Legal template
│   ├── knowledge_base_agent/           ← Knowledge Base Q&A template
│   ├── exec_assistant_agent/           ← Executive Assistant template
│   └── google_workspace_agent/         ← Google Workspace template
└── cli/
    ├── main.py                         ← click group: roscoe [init|monitor|eval]
    ├── init_command.py                 ← roscoe init (scaffold + wizard logic)
    ├── wizard_gui.py                   ← Tkinter GUI wizard
    ├── monitor_command.py              ← roscoe monitor
    ├── eval_command.py                 ← roscoe eval
    └── scaffold/                       ← files dropped by roscoe init
        ├── agent_config.yaml
        ├── main.py
        ├── tools/my_tools.py
        ├── prompts/system.txt
        ├── docs.md
        └── .env.example
```

---

## Test Suite: 121 Passing

```
tests/unit/test_config.py        — config loader + env var resolution
tests/unit/test_tools.py         — @tool decorator schema generation
tests/unit/test_core_types.py    — AgentResult fields + defaults
tests/unit/test_providers.py     — ProviderFactory + each built-in instantiation
tests/unit/test_middleware.py    — retry error selection, cost calc, audit format, rate limiter
tests/unit/test_memory.py        — conversation window, persistent store, knowledge search
tests/unit/test_connectors.py    — all 9 connectors (mocked httpx transport)
tests/unit/test_approval.py      — ApprovalGate decisions + PendingStore save/pop
tests/unit/test_monitoring.py    — metrics aggregation, dashboard render, alert thresholds
tests/unit/test_evals.py         — dataset loading, scorer math, EvalRunner, regression
tests/unit/test_templates.py     — template listing + path resolution
tests/unit/test_cli.py           — CLI command registration + scaffold output
tests/integration/test_e2e.py    — full end-to-end with real API (skipped without keys)
```

---

## Summary

ROSCOE is **Phases 0–10 complete**. The SDK is fully functional:

- Own ReAct loop (no LangGraph) — simple, debuggable, HITL-friendly
- 6 providers (+ custom) swappable via YAML
- 4 middleware layers auto-applied on every run
- 3 memory types (conversation, persistent, RAG)
- 9 enterprise connectors
- HITL with approve/reject/modify
- Monitoring dashboard + alerts + exporters
- Eval suite with 3 scorers + regression diffing
- CLI with GUI wizard + 6 templates
- 121 tests passing

**Remaining:** Phase 11 — publish to PyPI (wheel already built), write docs site, tag release.
