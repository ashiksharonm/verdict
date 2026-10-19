"""Typed results."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping


@dataclass(frozen=True)
class Verdict:
    """One check's outcome. ``flagged`` is ``score >= threshold``."""

    flagged: bool
    score: float
    threshold: float


@dataclass(frozen=True)
class CheckResult:
    """The outcome of checking one text: a :class:`Verdict` per requested check."""

    id: str
    model_version: str
    results: Dict[str, Verdict]
    latency_ms: float

    def __getitem__(self, check: str) -> Verdict:
        return self.results[check]

    @property
    def flagged(self) -> List[str]:
        """Names of the checks that fired."""
        return [c for c, v in self.results.items() if v.flagged]

    @classmethod
    def from_json(cls, d: Mapping[str, Any]) -> CheckResult:
        """Build from an API response object. Raises ``KeyError``/``TypeError``/``ValueError`` if malformed."""
        return cls(
            str(d["id"]),
            str(d["model_version"]),
            {c: Verdict(bool(v["flagged"]), float(v["score"]), float(v["threshold"])) for c, v in d["results"].items()},
            float(d["latency_ms"]),
        )
