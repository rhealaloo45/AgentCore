"""Hallucination scorer — LLM-as-judge over source documents.

Given the case's ``context_docs`` (the sources the agent was supposed to ground its
answer in) and the agent's answer, asks a judge what fraction of the answer's claims are
supported by the sources. Score 1.0 = fully grounded, 0.0 = entirely unsupported.

If a case has no ``context_docs``, there's nothing to ground against, so the scorer marks
itself not applicable rather than guessing.
"""

from __future__ import annotations

from typing import Any

from roscoe.evals.dataset import EvalCase
from roscoe.evals.scorers._judge import ask_score
from roscoe.evals.scorers.base import ActualRun, Scorer, ScoreResult

_PROMPT = """You are checking an AI answer for hallucinations against source documents.

Source documents:
{sources}

AI answer:
{answer}

What fraction of the claims in the answer are directly supported by the sources? Reply
with ONLY a number from 0 (no claims supported / fully hallucinated) to 10 (every claim
supported)."""


class HallucinationScorer(Scorer):
    name = "hallucination"

    def __init__(self, judge: Any) -> None:
        self._judge = judge

    def score(self, case: EvalCase, actual: ActualRun) -> ScoreResult:
        if not case.context_docs:
            return ScoreResult(self.name, 1.0, "no context docs; skipped", applicable=False)
        sources = "\n\n".join(f"[{i+1}] {doc}" for i, doc in enumerate(case.context_docs))
        prompt = _PROMPT.format(sources=sources, answer=actual.output)
        value, raw = ask_score(self._judge, prompt, scale=10.0)
        return ScoreResult(self.name, value, f"grounded fraction: {raw.strip()[:80]}")
