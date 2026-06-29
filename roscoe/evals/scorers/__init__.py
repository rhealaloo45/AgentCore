"""Scorers — each returns a float in [0,1] for one eval case."""

from roscoe.evals.scorers.base import ActualRun, Scorer, ScoreResult
from roscoe.evals.scorers.hallucination import HallucinationScorer
from roscoe.evals.scorers.output_quality import OutputQualityScorer
from roscoe.evals.scorers.tool_usage import ToolUsageScorer

__all__ = [
    "ActualRun",
    "Scorer",
    "ScoreResult",
    "ToolUsageScorer",
    "OutputQualityScorer",
    "HallucinationScorer",
]
