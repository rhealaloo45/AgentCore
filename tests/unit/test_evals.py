"""Phase 8 — evals tests.

Deterministic scorers run for real; LLM-judge scorers use a fake judge (no live LLM, per
the no-LLM-on-CI rule). EvalRunner runs against a fake agent.
"""

import json

import pytest

from roscoe.evals import (
    EvalCase,
    EvalRunner,
    HallucinationScorer,
    OutputQualityScorer,
    ToolUsageScorer,
    compare_runs,
    load_dataset,
    render_report,
    save_report,
)
from roscoe.evals.dataset import DatasetError
from roscoe.evals.scorers.base import ActualRun


# --- fakes ---


class FakeJudge:
    """Returns a fixed reply for every prompt (scale 0-10)."""

    def __init__(self, reply):
        self._reply = reply

    def invoke(self, prompt):
        class _Msg:
            content = self._reply

        return _Msg()


class FakeAgentResult:
    def __init__(self, output, tool_calls):
        self.output = output
        self.tool_calls = tool_calls


class FakeAgent:
    """Maps inputs to scripted (output, tool_calls)."""

    def __init__(self, mapping):
        self._mapping = mapping

    def run(self, user_input):
        output, tools = self._mapping[user_input]
        return FakeAgentResult(output, tools)


# --- dataset ---


def test_load_dataset_list_and_wrapped(tmp_path):
    p = tmp_path / "cases.json"
    p.write_text(json.dumps([{"input": "hi", "expected_tools": ["get_x"]}]))
    cases = load_dataset(p)
    assert len(cases) == 1
    assert cases[0].input == "hi"
    assert cases[0].expected_tools == ["get_x"]

    p2 = tmp_path / "wrapped.json"
    p2.write_text(json.dumps({"cases": [{"id": "c1", "input": "yo"}]}))
    assert load_dataset(p2)[0].id == "c1"


def test_load_dataset_missing_input_raises(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text(json.dumps([{"expected_output": "x"}]))
    with pytest.raises(DatasetError):
        load_dataset(p)


# --- tool usage scorer (deterministic) ---


def test_tool_usage_exact_match():
    case = EvalCase(id="1", input="x", expected_tools=["a", "b"])
    sr = ToolUsageScorer().score(case, ActualRun(output="", tool_sequence=["a", "b"]))
    assert sr.score == 1.0
    assert sr.applicable


def test_tool_usage_partial_and_order():
    case = EvalCase(id="1", input="x", expected_tools=["a", "b", "c"])
    # only a and c present in order -> LCS 2 / 3
    sr = ToolUsageScorer().score(case, ActualRun(output="", tool_sequence=["a", "x", "c"]))
    assert sr.score == pytest.approx(2 / 3)


def test_tool_usage_not_applicable_without_expected():
    case = EvalCase(id="1", input="x")
    sr = ToolUsageScorer().score(case, ActualRun(output="", tool_sequence=["a"]))
    assert not sr.applicable
    assert 0.0 <= sr.score <= 1.0


# --- LLM-judge scorers (fake judge) ---


def test_output_quality_parses_and_normalises():
    case = EvalCase(id="1", input="2+2?", expected_output="4")
    sr = OutputQualityScorer(FakeJudge("8")).score(case, ActualRun(output="4"))
    assert sr.score == pytest.approx(0.8)
    assert 0.0 <= sr.score <= 1.0


def test_output_quality_unparseable_scores_zero():
    case = EvalCase(id="1", input="x")
    sr = OutputQualityScorer(FakeJudge("no idea")).score(case, ActualRun(output="y"))
    assert sr.score == 0.0


def test_hallucination_needs_context_docs():
    case = EvalCase(id="1", input="x")  # no context docs
    sr = HallucinationScorer(FakeJudge("10")).score(case, ActualRun(output="y"))
    assert not sr.applicable


def test_hallucination_scores_grounding():
    case = EvalCase(id="1", input="x", context_docs=["the sky is blue"])
    sr = HallucinationScorer(FakeJudge("10")).score(case, ActualRun(output="the sky is blue"))
    assert sr.score == 1.0
    assert sr.applicable


def test_score_result_clamps_out_of_range():
    sr = OutputQualityScorer(FakeJudge("50")).score(  # 50/10 = 5.0 -> clamps to 1.0
        EvalCase(id="1", input="x"), ActualRun(output="y")
    )
    assert sr.score == 1.0


# --- eval runner + report ---


def _runner(agent, threshold=0.7, judge_reply="8"):
    return EvalRunner(
        agent,
        [ToolUsageScorer(), OutputQualityScorer(FakeJudge(judge_reply))],
        pass_threshold=threshold,
    )


def test_eval_runner_produces_report_and_verdict():
    cases = [
        EvalCase(id="c1", input="q1", expected_tools=["a"]),
        EvalCase(id="c2", input="q2", expected_tools=["a", "b"]),
    ]
    agent = FakeAgent({"q1": ("ans1", ["a"]), "q2": ("ans2", ["a", "b"])})
    report = _runner(agent).run(cases)

    assert len(report.case_results) == 2
    assert report.overall_scores["tool_usage"] == 1.0
    assert report.overall_scores["output_quality"] == pytest.approx(0.8)
    assert report.passed  # overall mean 0.9 >= 0.7
    assert "PASS" in render_report(report)


def test_eval_runner_fails_below_threshold():
    cases = [EvalCase(id="c1", input="q1", expected_tools=["a", "b"])]
    agent = FakeAgent({"q1": ("ans", [])})  # no tools called -> tool_usage 0
    report = _runner(agent, judge_reply="2").run(cases)  # quality 0.2
    assert not report.passed


def test_save_report_roundtrips(tmp_path):
    agent = FakeAgent({"q1": ("a", ["a"])})
    report = _runner(agent).run([EvalCase(id="c1", input="q1", expected_tools=["a"])])
    out = save_report(report, tmp_path / "r.json")
    data = json.loads(out.read_text())
    assert data["run_id"] == report.run_id
    assert data["passed"] is True


# --- regression diff ---


def test_compare_runs_shows_improvement_and_regression():
    cases = [EvalCase(id="c1", input="q1", expected_tools=["a", "b"])]
    # baseline: no tools -> tool_usage 0.0, quality 0.4
    base = _runner(FakeAgent({"q1": ("a", [])}), judge_reply="4").run(cases)
    # new: tools correct -> tool_usage 1.0, quality 0.9
    new = _runner(FakeAgent({"q1": ("a", ["a", "b"])}), judge_reply="9").run(cases)

    diff = compare_runs(base, new)
    assert diff.overall_delta > 0
    assert diff.scorer_deltas["tool_usage"] == 1.0
    assert any("tool_usage" in s for s in diff.improved)
    assert diff.regressed == []
