import numpy as np
import pytest
from verdict_evals.metrics import (
    best_threshold,
    bootstrap_ci,
    cohen_kappa,
    ece,
    latency_stats,
    paired_bootstrap_delta,
    point_metrics,
    recall_at_fpr,
)


def test_perfect_classifier():
    y = [0, 0, 1, 1]
    m = point_metrics(y, [0.0, 0.1, 0.9, 1.0])
    assert m["macro_f1"] == 1.0 and m["auroc"] == 1.0 and m["fpr"] == 0.0
    assert m["brier"] == pytest.approx((0.01 + 0.01) / 4)


def test_counts_match_hand_computation():
    y = [1, 1, 1, 0, 0, 0]
    p = [0.9, 0.8, 0.2, 0.7, 0.1, 0.1]
    m = point_metrics(y, p)
    # tp=2 fp=1 fn=1 tn=2
    assert m["precision"] == pytest.approx(2 / 3) and m["recall"] == pytest.approx(2 / 3)
    assert m["macro_f1"] == pytest.approx(2 / 3)


def test_ece_zero_when_calibrated_and_positive_when_overconfident():
    y = np.array([1] * 8 + [0] * 2)
    assert ece(y, np.full(10, 0.8)) == pytest.approx(0.0)
    assert ece(np.array([1, 0, 1, 0]), np.array([0.99, 0.99, 0.99, 0.99])) == pytest.approx(0.49)


def test_recall_at_fpr():
    y = np.array([0] * 100 + [1] * 10)
    p = np.concatenate([np.linspace(0, 0.5, 100), np.linspace(0.6, 1, 10)])
    assert recall_at_fpr(y, p, 0.01) == 1.0
    p2 = p.copy()
    p2[100:] = 0.0
    assert recall_at_fpr(y, p2, 0.05) == 0.0


def test_bootstrap_ci_brackets_point_and_is_seeded():
    rng = np.random.default_rng(0)
    y = rng.integers(0, 2, 300)
    p = np.clip(y * 0.6 + rng.normal(0.2, 0.2, 300), 0, 1)
    ci = bootstrap_ci(y, p, n_boot=200, seed=1)
    pm = point_metrics(y, p)
    assert ci["macro_f1"][0] <= pm["macro_f1"] <= ci["macro_f1"][1]
    assert ci == bootstrap_ci(y, p, n_boot=200, seed=1)


def test_paired_delta_and_kappa():
    y = np.array([0, 1] * 50)
    good = y * 0.9 + 0.05
    bad = np.full(100, 0.5)
    d = paired_bootstrap_delta(y, good, bad, lambda yy, pp: point_metrics(yy, pp)["auroc"], n_boot=100)
    assert d["delta"] == pytest.approx(0.5) and d["ci"][0] > 0
    assert cohen_kappa([0, 1, 0, 1], [0, 1, 0, 1]) == 1.0
    assert cohen_kappa([0, 1, 0, 1], [1, 0, 1, 0]) == pytest.approx(-1.0)


def test_latency_and_threshold():
    s = latency_stats([0.01] * 9 + [0.1], batch_size=1)
    assert s["p50_ms"] == pytest.approx(10.0) and s["p95_ms"] > 10
    y = [0] * 50 + [1] * 50
    p = [0.2] * 50 + [0.3] * 50
    t = best_threshold(y, p)
    assert 0.2 < t <= 0.3
