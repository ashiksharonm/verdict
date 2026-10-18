from __future__ import annotations

from collections.abc import Iterable, Mapping

from .models import CheckResult


def flag_rates(results: Iterable[CheckResult]) -> dict[str, float]:
    """Fraction of results that flagged, per check, over the results that ran that check."""
    seen: dict[str, int] = {}
    hit: dict[str, int] = {}
    for r in results:
        for c, v in r.results.items():
            seen[c] = seen.get(c, 0) + 1
            hit[c] = hit.get(c, 0) + int(v.flagged)
    return {c: hit[c] / seen[c] for c in seen}


def assert_checks(results: Iterable[CheckResult], max_rate: Mapping[str, float]) -> dict[str, float]:
    """CI gate: raise AssertionError if the flagged rate of any check exceeds its limit.

    `max_rate={"pii": 0.0, "prompt_injection": 0.02}` fails when any output leaks PII or more than 2%
    look like injections. A check named in `max_rate` that no result ran is an error, not a pass.
    Returns the measured rates.
    """
    results = list(results)
    rates = flag_rates(results)
    problems = []
    for check, limit in max_rate.items():
        if check not in rates:
            problems.append(f"{check}: no results ran this check")
        elif rates[check] > limit:
            n = sum(1 for r in results if check in r.results and r.results[check].flagged)
            problems.append(f"{check}: flagged rate {rates[check]:.3f} ({n}/{len(results)}) exceeds max {limit:.3f}")
    if problems:
        raise AssertionError("Verdict gate failed: " + "; ".join(problems))
    return rates
