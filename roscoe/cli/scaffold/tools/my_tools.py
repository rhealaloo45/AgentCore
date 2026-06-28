"""
Your agent's tools live here.

A tool is a plain Python function with type hints and a docstring, wrapped
with @tool. roscoe infers the JSON schema from the type hints — no manual
schema needed. The docstring is what the LLM reads to decide when to call
the tool, so make it specific.

Rules of thumb:
    - One tool = one action. Keep tools small and focused.
    - Return dicts or primitives — the LLM reads the return value.
    - The docstring should say WHEN to use it, not just what it does.
    - Don't catch exceptions inside tools — let them bubble up so the
      agent can report the error and the retry middleware can handle it.

Adding tools:
    1. Write a function with @tool below.
    2. Add it to the TOOLS list at the bottom.
    3. That's it — AgentRunner picks it up from the list.

Using connector tools alongside your own:
    from roscoe.connectors import GitHubConnector
    gh = GitHubConnector({"token": os.environ["GITHUB_TOKEN"]})
    TOOLS = [get_weather] + gh.tools

Sensitive tools (require human approval before running):
    List the tool's function name in agent_config.yaml:
        middleware:
          human_approval:
            require_approval_for: ["send_email", "delete_record"]
"""

from roscoe.tools import tool


@tool
def get_weather(city: str) -> dict:
    """Get the current weather for a city. Use when the user asks about weather."""
    # TODO: Replace this stub with a real API call (e.g. OpenWeatherMap).
    fake = {"london": "15C rainy", "delhi": "38C sunny", "tokyo": "22C clear"}
    return {"city": city, "weather": fake.get(city.lower(), "unknown")}


# @tool
# def search_docs(query: str) -> list[dict]:
#     """Search internal documents. Use when the user asks about company policies."""
#     # Hook up to your knowledge base, vector store, or API here.
#     return [{"title": "Example", "snippet": "..."}]


# @tool
# def send_email(to: str, subject: str, body: str) -> dict:
#     """Send an email. Use when the user explicitly asks to send a message."""
#     # Add to require_approval_for in agent_config.yaml for human sign-off.
#     return {"status": "sent", "to": to}


# ---------- Tool registry ----------------------------------------------------
# Every tool the agent can use must be in this list.
TOOLS = [get_weather]
