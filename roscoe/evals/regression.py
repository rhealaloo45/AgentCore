"""Regression diffing — compare two eval runs to see what improved or regressed.

Not a per-case scorer: it diffs two :class:`~roscoe.evals.eval_runner.EvalReport`
objects (the current run vs a baseline) and reports the delta per scorer and per case.
Kept at the evals top level (not under ``scorers/``) to avoid a circular import with the
runner it depends on.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from roscoe.evals.eval_runner import EvalReport


@dataclass
class RunDiff:
    """The delta between a baseline run (a) and a new run (b)."""

    overall_delta: float
    scorer_deltas: dict[str, float] = field(default_factory=dict)
    case_deltas: dict[str, dict[str, float]] = field(default_factory=dict)
    improved: list[str] = field(default_factory=list)
    regressed: list[str] = field(default_factory=list)


def compare_runs(run_a: EvalReport, run_b: EvalReport) -> RunDiff:
    """Diff ``run_b`` against baseline ``run_a`` (delta = b - a, positive = better)."""
    diff = RunDiff(overall_delta=round(run_b.overall_mean - run_a.overall_mean, 4))

    scorers = set(run_a.overall_scores) | set(run_b.overall_scores)
    for name in scorers:
        a = run_a.overall_scores.get(name, 0.0)
        b = run_b.overall_scores.get(name, 0.0)
        diff.scorer_deltas[name] = round(b - a, 4)

    a_cases = {cr.case_id: cr for cr in run_a.case_results}
    for cr_b in run_b.case_results:
        cr_a = a_cases.get(cr_b.case_id)
        if cr_a is None:
            continue
        per_case: dict[str, float] = {}
        for name, score_b in cr_b.scores.items():
            if name in cr_a.scores:
                delta = round(score_b - cr_a.scores[name], 4)
                per_case[name] = delta
                if delta > 0:
                    diff.improved.append(f"{cr_b.case_id}:{name}")
                elif delta < 0:
                    diff.regressed.append(f"{cr_b.case_id}:{name}")
        if per_case:
            diff.case_deltas[cr_b.case_id] = per_case

    return diff
