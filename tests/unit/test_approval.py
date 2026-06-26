"""Phase 6 — human-approval / HITL tests for the langgraph-free ReAct loop.

A scripted FakeModel returns pre-baked AIMessages, so the loop, the approval gate, and
pause/resume are exercised end-to-end with no live LLM.
"""

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import StructuredTool

from roscoe.approval.gate import ApprovalGate
from roscoe.core.agent_runner import AgentRunner
from roscoe.core.executor import ReactExecutor
from roscoe.middleware.rate_limiter import RateLimiter


class FakeModel:
    """Returns scripted AIMessages on each ``ainvoke``."""

    def __init__(self, replies):
        self._replies = list(replies)
        self._i = 0

    async def ainvoke(self, messages, *args, **kwargs):
        reply = self._replies[self._i]
        self._i += 1
        return reply


def _create_ticket(summary: str) -> dict:
    """Create a ticket."""
    return {"id": "INC1", "summary": summary}


def _ticket_tool():
    return StructuredTool.from_function(_create_ticket, name="create_ticket", description="Create a ticket.")


def _tool_call(name="create_ticket", args=None, cid="c1"):
    return {"name": name, "args": args or {"summary": "printer broken"}, "id": cid, "type": "tool_call"}


# --- ApprovalGate ---


def test_approval_gate_basics():
    gate = ApprovalGate(["send_email", "create_ticket"])
    assert gate.needs_approval("create_ticket")
    assert not gate.needs_approval("read_emails")
    assert gate.is_active
    assert not ApprovalGate([]).is_active


# --- Executor: gating + resume ---


async def test_executor_pauses_on_gated_tool_then_resumes_approve():
    ai_call = AIMessage(content="", tool_calls=[_tool_call()])
    ai_final = AIMessage(content="Ticket INC1 created.")
    ex = ReactExecutor(
        FakeModel([ai_call, ai_final]),
        [_ticket_tool()],
        approval_gate=ApprovalGate(["create_ticket"]),
    )

    res = await ex.run([HumanMessage(content="open a ticket")])
    assert res.status == "paused"
    assert res.pending_tool_calls[0]["name"] == "create_ticket"

    # human approves: run the held call, feed result back, continue
    convo = res.messages
    convo.append(await ex.exec_tool_call(res.pending_tool_calls[0]))
    res2 = await ex.resume(convo)
    assert res2.status == "success"
    assert res2.messages[-1].content == "Ticket INC1 created."


async def test_executor_runs_through_without_gate():
    ai_call = AIMessage(content="", tool_calls=[_tool_call()])
    ai_final = AIMessage(content="done")
    ex = ReactExecutor(FakeModel([ai_call, ai_final]), [_ticket_tool()])
    res = await ex.run([HumanMessage(content="open a ticket")])
    assert res.status == "success"
    assert res.messages[-1].content == "done"


async def test_executor_max_iterations_guard():
    # model always asks for a tool -> loop must stop and report error
    looping = [AIMessage(content="", tool_calls=[_tool_call(cid=f"c{i}")]) for i in range(5)]
    ex = ReactExecutor(FakeModel(looping), [_ticket_tool()], max_iterations=3)
    res = await ex.run([HumanMessage(content="loop")])
    assert res.status == "error"
    assert "Max iterations" in res.error


# --- AgentRunner: pause -> resume ---


def _runner(replies):
    ex = ReactExecutor(
        FakeModel(replies),
        [_ticket_tool()],
        approval_gate=ApprovalGate(["create_ticket"]),
    )
    return AgentRunner(
        config={},
        executor=ex,
        agent_name="t",
        provider="ollama",  # skips rate limiting; avoids needing real creds
        model="fake",
        middleware={"audit": {"enabled": False}},
        rate_limiter=RateLimiter(),
    )


async def test_runner_pause_then_approve():
    runner = _runner([AIMessage(content="", tool_calls=[_tool_call()]), AIMessage(content="Created INC1.")])
    res = await runner.arun("please open a ticket")
    assert res.status == "paused"
    assert res.pending_action["tool_calls"][0]["name"] == "create_ticket"

    resumed = await runner.aresume(res.run_id, "approve")
    assert resumed.status == "success"
    assert resumed.output == "Created INC1."


async def test_runner_pause_then_reject():
    runner = _runner([AIMessage(content="", tool_calls=[_tool_call()]), AIMessage(content="Okay, cancelled.")])
    res = await runner.arun("please open a ticket")
    assert res.status == "paused"

    resumed = await runner.aresume(res.run_id, "reject")
    assert resumed.status == "success"
    assert resumed.output == "Okay, cancelled."


async def test_resume_rejects_bad_decision():
    import pytest

    runner = _runner([AIMessage(content="", tool_calls=[_tool_call()]), AIMessage(content="x")])
    res = await runner.arun("ticket")
    with pytest.raises(ValueError):
        await runner.aresume(res.run_id, "maybe")
