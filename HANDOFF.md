# roscoe — Handoff Document (June 29, 2026)

## What is roscoe

**R**eady-to-run **O**rchestration **S**DK — **C**onfigurable, **O**bservable, **E**xtensible.

A Python SDK for building production-ready LLM agents. Provider-agnostic, built on
LangChain (no LangGraph), with middleware (retry, rate limiting, cost tracking, audit),
memory, HITL, connectors, evals, monitoring, and templates baked in.

---

## Current state

- **Version:** 0.1.3 (published/ready to publish on PyPI)
- **Tests:** 121 passing, 1 skipped (live Azure)
- **Branch:** `dev`
- **Uncommitted changes:** pyproject.toml, `roscoe/__init__.py` (version bump), 
  `roscoe/cli/eval_command.py` (sys.path + .env auto-load fix), 
  `roscoe/cli/wizard_gui.py` (scrollable GUI), `roscoe/cli/init_command.py` (GUI wizard + --cli/--quick flags),
  scaffold files (docs.md, fully commented agent_config.yaml, tools, prompts, .env.example),
  Google Workspace connector + template, README rewrite

---

## Repository layout

```
/Users/rhea/Desktop/AgentCore/          ← roscoe SDK source
/Users/rhea/Desktop/testing versions/ROSCOE complete/
  └── notion-agent/                     ← demo project for the video
```

---

## Key files in AgentCore (SDK)

| File | What it does |
|---|---|
| `roscoe/core/executor.py` | Hand-rolled async ReAct loop (~100 lines, no LangGraph) |
| `roscoe/core/agent_runner.py` | Main API: `AgentRunner.from_config()`, `.run()`, `.resume()` |
| `roscoe/approval/gate.py` | HITL: `ApprovalGate`, `PendingStore`, pause/resume |
| `roscoe/middleware/` | retry, rate_limiter (token bucket), cost_tracker, audit_logger |
| `roscoe/memory/` | conversation (windowed), persistent (sqlite), knowledge (RAG) |
| `roscoe/connectors/` | REST, Jira, ServiceNow, Outlook, SharePoint, GitHub, Notion, Google Workspace, Snowflake (9 total) |
| `roscoe/monitoring/` | metrics aggregation, dashboard, alerts, Prometheus + Azure exporters |
| `roscoe/evals/` | dataset, scorers (tool_usage, output_quality, hallucination), eval_runner, regression diffing |
| `roscoe/templates/` | 6 templates: hr, it_support, legal, knowledge_base, exec_assistant, google_workspace |
| `roscoe/cli/` | `roscoe init` (GUI wizard + CLI wizard), `roscoe monitor`, `roscoe eval` |
| `roscoe/cli/wizard_gui.py` | Tkinter GUI wizard (scrollable, card-based layout) |
| `roscoe/cli/scaffold/` | Files dropped by `roscoe init` — all heavily commented |
| `README.md` | Full feature docs, PyPI landing page |

---

## Demo project: notion-agent

**Location:** `/Users/rhea/Desktop/testing versions/ROSCOE complete/notion-agent/`

**What it does:** Chat agent connected to Notion + web search via OpenRouter. Searches your
cloud computing study progress in Notion, creates study plans, saves them back to Notion
with HITL approval.

### Files

| File | Purpose |
|---|---|
| `agent_config.yaml` | OpenRouter (gpt-oss-120b:free), HITL on `create_page`, all middleware on |
| `tools/my_tools.py` | Notion search/get_page + custom `create_page` (handles databases + pages, auto-detects title property, converts markdown to Notion blocks) + `search_web` (DuckDuckGo) |
| `prompts/system.txt` | Study planner persona, workflow instructions, "never ask for IDs" rule |
| `chat_ui.py` | Flask web UI — chat window, typing indicator, HITL approve/reject buttons, markdown rendering (via marked.js), status bar with token/cost |
| `main.py` | Terminal chat mode with HITL |
| `.env` | Has OPENROUTER_API_KEY + NOTION_TOKEN (ROTATE THESE — they were shared in chat) |
| `evals/test_cases.json` | 3 cases: check-progress, create-study-plan, greeting |

### Running it

```bash
cd "/Users/rhea/Desktop/testing versions/ROSCOE complete/notion-agent"
source "../.venv/bin/activate"

# Web UI
python chat_ui.py          # opens http://localhost:5000

# Terminal
python main.py

# Monitor
roscoe monitor --path logs/audit.jsonl

# Evals
roscoe eval --dataset evals/test_cases.json --config agent_config.yaml --tools tools.my_tools:TOOLS
```

### Known issues / quirks

1. **Free model rate limits** — `openai/gpt-oss-120b:free` hits 429s under load. Switch to `openai/gpt-oss-20b:free` or a paid model if it's flaky.
2. **Notion integration access** — pages must be explicitly shared with the "ROSCOE" integration in Notion (⋯ → Connections → Connect to).
3. **Database vs page parent** — the `create_page` tool auto-detects whether the parent ID is a database or page and uses the correct API. It also finds the title property name dynamically (your database uses `Name`, not `title`).
4. **Eval runs are slow** — each case is a live LLM call. 3 cases ≈ 1 min on free model.

---

## What's done

- [x] Phases 0–10 complete (core, middleware, memory, connectors, HITL, monitoring, evals, templates, CLI)
- [x] LangGraph fully removed — own ReAct loop
- [x] GUI wizard for `roscoe init` (Tkinter, scrollable, card layout)
- [x] CLI wizard fallback (`--cli` flag)
- [x] `--quick` flag to skip wizard
- [x] 9 connectors (added Google Workspace)
- [x] 6 templates (added google_workspace_agent)
- [x] `docs.md` ships with every scaffolded project (16-section developer guide)
- [x] README rewritten for PyPI (full feature docs)
- [x] Secret scan — clean
- [x] Build passing: wheel + sdist + `twine check` ✓
- [x] Version 0.1.3 built, ready to publish
- [x] Notion demo agent working (search, plan, HITL create page)
- [x] Flask chat UI with markdown rendering
- [x] Eval command fixed (sys.path + .env auto-load)

---

## What's NOT done / next steps

### Immediate (before video)

- [ ] **Rotate API keys** — OpenRouter + Notion tokens were shared in chat. Regenerate them.
- [ ] **Commit all changes** — lots of uncommitted work on `dev` branch
- [ ] **Test the full video flow end-to-end** — init → wizard → chat → HITL → monitor → eval
- [ ] **Gradio removed** — can uninstall it from the venv if you want (`pip uninstall gradio`)

### Video recording flow

1. `roscoe init notion-agent` → GUI wizard → Create Project
2. Show generated files (agent_config.yaml, tools, prompts, docs.md)
3. Show the 3 things you changed (.env, tools, prompt)
4. `python chat_ui.py` → browser chat
5. Ask about progress → agent searches Notion → shows table
6. Ask for study plan → agent creates day-by-day plan
7. "Save to Notion" → HITL approval → approve → page created
8. Cut to Notion → show the page
9. `roscoe monitor` → dashboard
10. `roscoe eval` → scores
11. Provider swap (change one YAML line)
12. Close: "pip install roscoe"

### Future (post-video)

- [ ] Phase 11 — Packaging & launch (PyPI publish, lockfile, badges)
- [ ] CI/CD pipeline (GitHub Actions)
- [ ] Async HITL (webhook/callback instead of in-memory)
- [ ] Streaming responses in chat UI
- [ ] More eval scorers
- [ ] OpenTelemetry integration

---

## Important constraints

- **PLAN.md** — local only, gitignored. Do NOT commit.
- **test_steps.md** — local only, gitignored. Do NOT commit.
- **.env files** — never commit. Gitignored.
- **Employer IP sign-off** — required before public PyPI publish (work-for-hire gate).
- **Commit messages** — end with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

## Publish commands

```bash
cd /Users/rhea/Desktop/AgentCore
source .venv/bin/activate
twine upload dist/*
# Username: __token__
# Password: pypi-YOUR_TOKEN
```

Update in the demo venv after publish:
```bash
pip install --upgrade roscoe
```
