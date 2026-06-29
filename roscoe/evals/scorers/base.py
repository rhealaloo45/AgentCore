"""Scorer base types.

Every scorer takes an :class:`~roscoe.evals.dataset.EvalCase` and the agent's
:class:`ActualRun`, and returns a :class:`ScoreResult` with a float in ``[0.0, 1.0]``
(1.0 = best). Scorers that don't apply to a case (e.g. tool-usage with no
``expected_tools``) return ``applicable=False`` so the runner can skip them in averages.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ActualRun:
    """What the agent actually produced for one case."""

    output: str
    tool_sequence: list[str] = field(default_factory=list)


@dataclass
class ScoreResult:
    """A single scorer's verdict on one case."""

    name: str
    score: float
    detail: str = ""
    applicable: bool = True

    def __post_init__(self) -> None:
        # Clamp defensively so a misbehaving LLM judge can't push scores out of range.
        self.score = max(0.0, min(1.0, float(self.score)))


class Scorer(ABC):
    """Base class for all scorers."""

    name: str = "scorer"

    @abstractmethod
    def score(self, case: "object", actual: ActualRun) -> ScoreResult: ...
