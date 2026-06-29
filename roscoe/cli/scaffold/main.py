"""
Entry point for __PROJECT_NAME__.

Run:
    python main.py

This file is intentionally minimal. All configuration lives in
agent_config.yaml — edit that file to change providers, middleware, memory,
or approval gates. Your tools live in tools/my_tools.py.

Multi-turn example (pass user_id + session_id for memory):
    result = agent.run("Hi, I'm Rhea.", user_id="u1", session_id="s1")
    result = agent.run("What's my name?", user_id="u1", session_id="s1")

Async usage:
    import asyncio
    result = asyncio.run(agent.arun("What's the weather?"))

Human approval (if configured in agent_config.yaml):
    result = agent.run("Send the email")
    if result.status == "paused":
        # Inspect result.pending_action, then:
        result = agent.resume(result.run_id, "approve")   # or "reject"
"""

from roscoe import AgentRunner

from tools.my_tools import TOOLS

agent = AgentRunner.from_config("agent_config.yaml", tools=TOOLS)

if __name__ == "__main__":
    result = agent.run("What's the weather in London?")

    print("OUTPUT:", result.output)
    print("STATUS:", result.status)          # success | error | paused
    print("TOKENS:", result.total_tokens)
    print("COST  :", result.cost_usd)        # USD estimate (None if model not in cost table)
    print("RUN_ID:", result.run_id)          # ties to audit log in logs/audit.jsonl

    if result.status == "error":
        print("ERROR :", result.error)
