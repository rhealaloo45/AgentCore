"""Evals — automated scoring of agent outputs to catch regressions before deploy."""

from roscoe.evals.dataset import DatasetError, EvalCase, load_dataset
from roscoe.evals.eval_runner import CaseResult, EvalReport, EvalRunner
from roscoe.evals.regression import RunDiff, compare_runs
from roscoe.evals.report import render_report, save_report, to_dict
from roscoe.evals.scorers import (
    ActualRun,
    HallucinationScorer,
    OutputQualityScorer,
    Scorer,
    ScoreResult,
    ToolUsageScorer,
)

__all__ = [
    "EvalCase",
    "load_dataset",
    "DatasetError",
    "EvalRunner",
    "EvalReport",
    "CaseResult",
    "render_report",
    "save_report",
    "to_dict",
    "ActualRun",
    "Scorer",
    "ScoreResult",
    "ToolUsageScorer",
    "OutputQualityScorer",
    "HallucinationScorer",
    "RunDiff",
    "compare_runs",
]
