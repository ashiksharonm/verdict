from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Verdict:
    """One check's outcome. `flagged` is `score >= threshold`."""

    flagged: bool
    score: float
    threshold: float


@dataclass(frozen=True)
class CheckResult:
    id: str
    model_version: str
    results: dict[str, Verdict]
    latency_ms: float

    def __getitem__(self, check: str) -> Verdict:
        return self.results[check]

    @property
    def flagged(self) -> list[str]:
        return [c for c, v in self.results.items() if v.flagged]

    @classmethod
    def from_json(cls, d: dict[str, Any]) -> CheckResult:
        return cls(d["id"], d["model_version"],
                   {c: Verdict(bool(v["flagged"]), float(v["score"]), float(v["threshold"])) for c, v in d["results"].items()},
                   float(d["latency_ms"]))
