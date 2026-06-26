"""EvalRunner — orchestrates scorers over a dataset and produces a scored report.

Runs each test case through an agent (anything with ``.run(input) -> AgentResult``),
applies every scorer, and aggregates per-scorer and overall means. Each run is stamped
with a UUID and timestamp so two runs can be diffed (see ``regression.compare_runs``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from statistics import mean
from typing import Any, Sequence
from uuid import uuid4

from roscoe.evals.dataset import EvalCase
from roscoe.evals.scorers.base import ActualRun, Scorer


@dataclass
class CaseResult:
    """Per-case scores from one eval run."""

    case_id: str
    output: str
    scores: dict[str, float] = field(default_factory=dict)  # applicable scorers only
    details: dict[str, str] = field(default_factory=dict)


@dataclass
class EvalReport:
    """Result of running a dataset through the scorers."""

    run_id: str
    timestamp: str
    pass_threshold: float
    case_results: list[CaseResult]
    overall_scores: dict[str, float]  # per-scorer mean across applicable cases
    overall_mean: float
    passed: bool


class EvalRunner:
    """Runs an agent over a dataset and scores each output."""

    def __init__(
        self,
        agent: Any,
        scorers: Sequence[Scorer],
        *,
        pass_threshold: float = 0.7,
    ) -> None:
        self._agent = agent
        self._scorers = list(scorers)
        self._pass_threshold = pass_threshold

    def run(self, cases: Sequence[EvalCase]) -> EvalReport:
        case_results: list[CaseResult] = []
        per_scorer: dict[str, list[float]] = {}

        for case in cases:
            result = self._agent.run(case.input)
            actual = ActualRun(output=result.output, tool_sequence=list(result.tool_calls))

            cr = CaseResult(case_id=case.id, output=actual.output)
            for scorer in self._scorers:
                sr = scorer.score(case, actual)
                if not sr.applicable:
                    continue
                cr.scores[sr.name] = sr.score
                cr.details[sr.name] = sr.detail
                per_scorer.setdefault(sr.name, []).append(sr.score)
            case_results.append(cr)

        overall_scores = {name: round(mean(vals), 4) for name, vals in per_scorer.items()}
        overall_mean = round(mean(overall_scores.values()), 4) if overall_scores else 0.0

        return EvalReport(
            run_id=str(uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            pass_threshold=self._pass_threshold,
            case_results=case_results,
            overall_scores=overall_scores,
            overall_mean=overall_mean,
            passed=overall_mean >= self._pass_threshold,
        )
