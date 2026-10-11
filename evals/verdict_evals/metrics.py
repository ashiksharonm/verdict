"""Metrics for binary guardrail checks, with seeded bootstrap confidence intervals.

Every system produces, per example, a score in [0, 1]: its probability (or a 0/1 hard decision)
that the check fires. Thresholded decisions use the threshold that system was given (0.5 unless
tuned on validation).
"""
from __future__ import annotations

from collections.abc import Callable, Sequence

import numpy as np
from sklearn.metrics import roc_auc_score, roc_curve

ECE_BINS = 15


def _f1(tp: float, fp: float, fn: float) -> float:
    denom = 2 * tp + fp + fn
    return 0.0 if denom == 0 else 2 * tp / denom


def confusion(y: np.ndarray, pred: np.ndarray) -> tuple[int, int, int, int]:
    tp = int(np.sum((pred == 1) & (y == 1)))
    fp = int(np.sum((pred == 1) & (y == 0)))
    fn = int(np.sum((pred == 0) & (y == 1)))
    tn = int(np.sum((pred == 0) & (y == 0)))
    return tp, fp, fn, tn


def ece(y: np.ndarray, p: np.ndarray, bins: int = ECE_BINS) -> float:
    """Top-label expected calibration error over equal-width confidence bins."""
    pred = (p >= 0.5).astype(int)
    conf = np.where(pred == 1, p, 1 - p)
    correct = (pred == y).astype(float)
    edges = np.linspace(0.5, 1.0, bins + 1)
    idx = np.clip(np.digitize(conf, edges[1:-1], right=True), 0, bins - 1)
    total = 0.0
    for b in range(bins):
        m = idx == b
        if m.any():
            total += m.mean() * abs(correct[m].mean() - conf[m].mean())
    return float(total)


def recall_at_fpr(y: np.ndarray, p: np.ndarray, max_fpr: float) -> float:
    """Highest recall reachable with false-positive rate <= `max_fpr` (from the ROC curve)."""
    if len(np.unique(y)) < 2:
        return float("nan")
    fpr, tpr, _ = roc_curve(y, p)
    ok = fpr <= max_fpr + 1e-12
    return float(tpr[ok].max()) if ok.any() else 0.0


def point_metrics(y: Sequence[int], p: Sequence[float], threshold: float = 0.5) -> dict[str, float]:
    y = np.asarray(y, dtype=int)
    p = np.clip(np.asarray(p, dtype=float), 0.0, 1.0)
    pred = (p >= threshold).astype(int)
    tp, fp, fn, tn = confusion(y, pred)
    f1_pos = _f1(tp, fp, fn)
    f1_neg = _f1(tn, fn, fp)
    two_classes = len(np.unique(y)) == 2
    return {
        "n": int(len(y)),
        "positives": int(y.sum()),
        "accuracy": float((pred == y).mean()) if len(y) else float("nan"),
        "precision": tp / (tp + fp) if tp + fp else 0.0,
        "recall": tp / (tp + fn) if tp + fn else 0.0,
        "f1": f1_pos,
        "macro_f1": (f1_pos + f1_neg) / 2,
        "fpr": fp / (fp + tn) if fp + tn else 0.0,
        "auroc": float(roc_auc_score(y, p)) if two_classes else float("nan"),
        "ece": ece(y, p),
        "brier": float(np.mean((p - y) ** 2)),
        "recall_at_fpr_1": recall_at_fpr(y, p, 0.01),
        "recall_at_fpr_5": recall_at_fpr(y, p, 0.05),
    }


CI_METRICS = ("macro_f1", "f1", "precision", "recall", "auroc", "ece", "brier", "recall_at_fpr_5")


def bootstrap_ci(y: Sequence[int], p: Sequence[float], threshold: float = 0.5, n_boot: int = 1000,
                 seed: int = 0, metrics: Sequence[str] = CI_METRICS,
                 alpha: float = 0.05) -> dict[str, list[float]]:
    """Percentile bootstrap CI for each metric (resampling examples with replacement)."""
    y = np.asarray(y, dtype=int)
    p = np.asarray(p, dtype=float)
    rng = np.random.default_rng(seed)
    draws: dict[str, list[float]] = {m: [] for m in metrics}
    n = len(y)
    for _ in range(n_boot):
        i = rng.integers(0, n, n)
        if len(np.unique(y[i])) < 2:
            continue
        pm = point_metrics(y[i], p[i], threshold)
        for m in metrics:
            draws[m].append(pm[m])
    out = {}
    for m, vals in draws.items():
        v = np.asarray([x for x in vals if not np.isnan(x)])
        out[m] = ([float(np.quantile(v, alpha / 2)), float(np.quantile(v, 1 - alpha / 2))]
                  if len(v) else [float("nan"), float("nan")])
    return out


def paired_bootstrap_delta(y: Sequence[int], p_a: Sequence[float], p_b: Sequence[float],
                           metric: Callable[[np.ndarray, np.ndarray], float], n_boot: int = 1000,
                           seed: int = 0) -> dict[str, float]:
    """Mean and 95% CI of metric(a) - metric(b) on the same resampled examples."""
    y, a, b = (np.asarray(x, dtype=float) for x in (y, p_a, p_b))
    rng = np.random.default_rng(seed)
    deltas = []
    for _ in range(n_boot):
        i = rng.integers(0, len(y), len(y))
        if len(np.unique(y[i])) < 2:
            continue
        deltas.append(metric(y[i], a[i]) - metric(y[i], b[i]))
    d = np.asarray(deltas)
    return {"delta": float(metric(y, a) - metric(y, b)), "ci": [float(np.quantile(d, 0.025)),
                                                                 float(np.quantile(d, 0.975))]}


def cohen_kappa(a: Sequence[int], b: Sequence[int]) -> float:
    a = np.asarray(a, dtype=int)
    b = np.asarray(b, dtype=int)
    po = float((a == b).mean())
    pa, pb = a.mean(), b.mean()
    pe = pa * pb + (1 - pa) * (1 - pb)
    return float((po - pe) / (1 - pe)) if pe < 1 else 1.0


def latency_stats(seconds: Sequence[float], batch_size: int = 1) -> dict[str, float]:
    """p50/p95 per-call latency in ms and items/s throughput from per-call wall times."""
    s = np.asarray(seconds, dtype=float)
    return {
        "calls": int(len(s)),
        "batch_size": int(batch_size),
        "p50_ms": float(np.percentile(s, 50) * 1000),
        "p95_ms": float(np.percentile(s, 95) * 1000),
        "throughput_per_s": float(len(s) * batch_size / s.sum()) if s.sum() > 0 else float("nan"),
    }


def best_threshold(y: Sequence[int], p: Sequence[float]) -> float:
    """Threshold maximising macro-F1 (used on validation only)."""
    y = np.asarray(y, dtype=int)
    p = np.asarray(p, dtype=float)
    cands = np.unique(np.concatenate([np.linspace(0.05, 0.95, 91), np.quantile(p, np.linspace(0, 1, 101))]))
    best, best_t = -1.0, 0.5
    for t in cands:
        m = point_metrics(y, p, float(t))["macro_f1"]
        if m > best + 1e-12:
            best, best_t = m, float(t)
    return best_t
