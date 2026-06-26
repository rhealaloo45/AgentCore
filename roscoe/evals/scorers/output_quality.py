"""Output-quality scorer — LLM-as-judge.

Asks a judge model to rate how well the agent's answer addresses the input (and matches
the expected answer, when one is provided) on a 0-10 scale, normalised to ``[0,1]``.
Unit-tested with a fake judge; the real LLM check is the integration test.
"""

from __future__ import annotations

from typing import Any

from roscoe.evals.dataset import EvalCase
from roscoe.evals.scorers._judge import ask_score
from roscoe.evals.scorers.base import ActualRun, Scorer, ScoreResult

_PROMPT = """You are grading an AI assistant's answer.

User input:
{input}
{expected}
Assistant answer:
{answer}

Rate the answer's quality from 0 (useless or wrong) to 10 (excellent, fully correct and
helpful). Reply with ONLY the number."""


class OutputQualityScorer(Scorer):
    name = "output_quality"

    def __init__(self, judge: Any) -> None:
        self._judge = judge

    def score(self, case: EvalCase, actual: ActualRun) -> ScoreResult:
        expected = (
            f"\nReference answer (for comparison):\n{case.expected_output}\n"
            if case.expected_output
            else ""
        )
        prompt = _PROMPT.format(input=case.input, expected=expected, answer=actual.output)
        value, raw = ask_score(self._judge, prompt, scale=10.0)
        return ScoreResult(self.name, value, f"judge said: {raw.strip()[:80]}")
