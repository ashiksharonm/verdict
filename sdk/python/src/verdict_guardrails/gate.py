from __future__ import annotations

from typing import Dict, Iterable, List, Mapping

from .models import CheckResult


def flag_rates(results: Iterable[CheckResult]) -> Dict[str, float]:
    """Fraction of results that flagged, per check, over the results that ran that check."""
    seen: Dict[str, int] = {}
    hit: Dict[str, int] = {}
    for r in results:
        for c, v in r.results.items():
            seen[c] = seen.get(c, 0) + 1
            hit[c] = hit.get(c, 0) + int(v.flagged)
    return {c: hit[c] / seen[c] for c in seen}


def assert_checks(results: Iterable[CheckResult], max_rate: Mapping[str, float]) -> Dict[str, float]:
    """CI gate: raise AssertionError if the flagged rate of any check exceeds its limit.

    `max_rate={"pii": 0.0, "prompt_injection": 0.02}` fails when any output leaks PII or more than 2%
    look like injections. A check named in `max_rate` that no result ran is an error, not a pass.
    Returns the measured rates.
    """
    items = list(results)
    rates = flag_rates(items)
    problems: List[str] = []
    for check, limit in max_rate.items():
        if check not in rates:
            problems.append(f"{check}: no results ran this check")
        elif rates[check] > limit:
            ran = [r.results[check] for r in items if check in r.results]
            n = sum(1 for v in ran if v.flagged)
            problems.append(f"{check}: {n}/{len(ran)} flagged ({rates[check]:.1%}), max allowed {limit:.1%}")
    if problems:
        raise AssertionError("Verdict gate failed:\n  " + "\n  ".join(problems))
    return rates
