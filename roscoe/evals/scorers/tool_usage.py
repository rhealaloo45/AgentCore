"""Tool-usage scorer — deterministic, no LLM.

Compares the agent's actual tool-call sequence against the case's ``expected_tools``.
Score is order-aware: the longest common subsequence between expected and actual,
divided by the number of expected tools. So calling the right tools in the right order
scores 1.0; missing or out-of-order calls score lower; extra tools don't help but the
penalty comes from missed expectations.
"""

from __future__ import annotations

from roscoe.evals.dataset import EvalCase
from roscoe.evals.scorers.base import ActualRun, Scorer, ScoreResult


class ToolUsageScorer(Scorer):
    name = "tool_usage"

    def score(self, case: EvalCase, actual: ActualRun) -> ScoreResult:
        expected = case.expected_tools
        if not expected:
            return ScoreResult(self.name, 1.0, "no expected tools; skipped", applicable=False)

        matched = _lcs_len(expected, actual.tool_sequence)
        score = matched / len(expected)
        detail = f"matched {matched}/{len(expected)} expected (in order); actual={actual.tool_sequence}"
        return ScoreResult(self.name, score, detail)


def _lcs_len(a: list[str], b: list[str]) -> int:
    """Length of the longest common subsequence of two lists."""
    if not a or not b:
        return 0
    prev = [0] * (len(b) + 1)
    for x in a:
        curr = [0] * (len(b) + 1)
        for j, y in enumerate(b, start=1):
            curr[j] = prev[j - 1] + 1 if x == y else max(prev[j], curr[j - 1])
        prev = curr
    return prev[len(b)]
