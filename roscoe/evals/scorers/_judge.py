"""Shared helpers for LLM-as-judge scorers.

A "judge" is any object with an ``.invoke(prompt) -> message`` method whose result has a
``.content`` string — i.e. a LangChain chat model, or roscoe itself. Tests inject a fake
judge so these scorers run with no live LLM.
"""

from __future__ import annotations

import re
from typing import Any

_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


def ask_score(judge: Any, prompt: str, *, scale: float = 10.0) -> tuple[float, str]:
    """Send ``prompt`` to the judge and parse a normalised ``[0,1]`` score.

    The judge is asked to answer with a number on ``0..scale``; the first number in the
    reply is taken and divided by ``scale``. Returns ``(score, raw_reply)``. An
    unparseable reply scores ``0.0`` so a broken judge fails loudly rather than silently
    passing.
    """
    reply = judge.invoke(prompt)
    raw = getattr(reply, "content", reply)
    raw = raw if isinstance(raw, str) else str(raw)
    match = _NUMBER.search(raw)
    if not match:
        return 0.0, raw
    value = float(match.group()) / scale
    return max(0.0, min(1.0, value)), raw
