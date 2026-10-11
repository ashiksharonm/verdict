"""Benchmark every system on the held-out test splits and write results + report.

    python -m verdict_evals.run --out evals/results/2026-10-11            # full run (`make bench`)
    python -m verdict_evals.run --fixture --systems tfidf keyword --out /tmp/smoke   # CI smoke

Outputs: `results.json` (all metrics, CIs, latency, environment), `predictions.jsonl` (per-item
scores) and `report.md`.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import platform
import random
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
from verdict_train.checks import CHECK_NAMES
from verdict_train.data.common import read_jsonl

from .metrics import bootstrap_ci, cohen_kappa, latency_stats, paired_bootstrap_delta, point_metrics
from .obfuscate import TRANSFORMS, obfuscate

FT_DIR = "artifacts/verdict-laya"
INT8 = "artifacts/onnx/model.int8.onnx"
FP32_ONNX = "artifacts/onnx/model.onnx"
LLM_JUDGE_N = 200  # per check, stratified, fixed seed
LATENCY_N = 200
N_BOOT = 1000
SEED = 13


def system_factories(args) -> dict[str, Callable[[], Any]]:
    from . import systems as S

    return {
        "laya_ft": lambda: S.LayaSystem("Verdict (Laya fine-tuned, fp32)", FT_DIR, device=args.device),
        "laya_ft_int8": lambda: S.LayaSystem("Verdict (Laya fine-tuned, ONNX int8)", FT_DIR, onnx_path=INT8),
        "laya_zeroshot": lambda: S.LayaSystem("Laya zero-shot (base)", "convaiinnovations/laya",
                                              device=args.device, calibrated=False),
        "laya_td_zeroshot": lambda: S.LayaSystem("Laya zero-shot (typed-decisions)",
                                                 "convaiinnovations/laya-typed-decisions",
                                                 device=args.device, calibrated=False, max_len=512),
        "presidio": S.PresidioSystem,
        "keyword": S.KeywordSystem,
        "nli": lambda: S.NliSystem(device=args.device),
        "protectai": lambda: S.ProtectAISystem(device=args.device),
        "llm_judge": lambda: S.LlmJudgeSystem(args.judge_model, device=args.device),
        # latency-only variants (same weights as laya_ft / laya_ft_int8)
        "laya_ft_cpu": lambda: S.LayaSystem("Verdict fp32 (PyTorch CPU)", FT_DIR, device="cpu"),
        "laya_ft_onnx_fp32": lambda: S.LayaSystem("Verdict fp32 (ONNX CPU)", FT_DIR, onnx_path=FP32_ONNX),
    }


def stratified_subsample(records: list[dict], n: int, seed: int) -> list[dict]:
    if len(records) <= n:
        return list(records)
    rng = random.Random(seed)
    pos = [r for r in records if r["label"] == 1]
    neg = [r for r in records if r["label"] == 0]
    k = round(n * len(pos) / len(records))
    return sorted(rng.sample(pos, k) + rng.sample(neg, n - k), key=lambda r: r["id"])


def evaluate(y, p, thr, n_boot) -> dict[str, Any]:
    return {"threshold": thr, **point_metrics(y, p, thr),
            "ci95": bootstrap_ci(y, p, thr, n_boot=n_boot, seed=SEED)}


def by_source(records, p, thr) -> dict[str, Any]:
    out = {}
    for src in sorted({r["source"] for r in records}):
        idx = [i for i, r in enumerate(records) if r["source"] == src]
        y = np.array([records[i]["label"] for i in idx])
        m = point_metrics(y, p[idx], thr)
        out[src] = {k: m[k] for k in ("n", "positives", "accuracy", "macro_f1", "recall", "fpr")}
    return out


def batch1_latency(system, sample: list[dict]) -> dict[str, Any]:
    saved, system.batch_size = system.batch_size, 1
    try:
        system.score(sample[:5])  # warm-up
        _, times, _ = system.score(sample)
    finally:
        system.batch_size = saved
    return latency_stats(times, 1)


def environment(device: str) -> dict[str, Any]:
    import importlib.metadata as md

    env = {"date": dt.date.today().isoformat(), "machine": "Apple M5, 16 GB unified memory",
           "platform": platform.platform(), "python": platform.python_version(), "device": device}
    for pkg in ("laya", "torch", "transformers", "onnxruntime", "presidio-analyzer", "scikit-learn"):
        try:
            env[pkg] = md.version(pkg)
        except md.PackageNotFoundError:
            pass
    return env


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", required=True)
    ap.add_argument("--data-dir", default="data/processed")
    ap.add_argument("--systems", nargs="*", default=["laya_ft", "laya_ft_int8", "laya_zeroshot",
                                                     "laya_td_zeroshot", "presidio", "keyword", "nli",
                                                     "protectai", "llm_judge"])
    ap.add_argument("--latency-only", nargs="*", default=["laya_ft_cpu", "laya_ft_onnx_fp32"])
    ap.add_argument("--device", default="mps")
    ap.add_argument("--judge-model", default="Qwen/Qwen3-1.7B")
    ap.add_argument("--judge-n", type=int, default=LLM_JUDGE_N)
    ap.add_argument("--n-boot", type=int, default=N_BOOT)
    ap.add_argument("--limit", type=int, default=0, help="cap test items per check (debugging)")
    ap.add_argument("--fixture", action="store_true", help="use tests/fixtures/mini.jsonl (CI smoke)")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    if args.fixture:
        fx = read_jsonl(Path(__file__).resolve().parents[2] / "tests/fixtures/mini.jsonl")
        test = {c: [r for r in fx if r["check"] == c] for c in CHECK_NAMES}
    else:
        test = {c: read_jsonl(Path(args.data_dir) / c / "test.jsonl") for c in CHECK_NAMES}
    if args.limit:
        test = {c: stratified_subsample(v, args.limit, SEED) for c, v in test.items()}
    judge_sets = {c: stratified_subsample(v, args.judge_n, SEED) for c, v in test.items()}
    inj_pos = [r for r in test["prompt_injection"] if r["label"] == 1]
    robust_sets = {name: obfuscate(inj_pos, name, SEED) for name in TRANSFORMS}
    rng = np.random.default_rng(SEED)

    from . import systems as S

    factories = system_factories(args)
    factories["tfidf"] = lambda: S.TfidfSystem([r for v in test.values() for r in v])
    results: dict[str, Any] = {"environment": environment(args.device), "fixture": args.fixture,
                               "test_sizes": {c: len(v) for c, v in test.items()},
                               "llm_judge_n_per_check": args.judge_n, "n_boot": args.n_boot,
                               "systems": {}}
    preds: dict[str, dict[str, float]] = {}

    for key in args.systems:
        system = factories[key]()
        print(f"== {system.name}", flush=True)
        entry: dict[str, Any] = {**system.describe(), "checks": {}, "robustness": {}}
        is_judge = key == "llm_judge"
        all_times: list[float] = []
        for check in system.checks:
            recs = judge_sets[check] if is_judge else test[check]
            p, times, bs = system.score(recs)
            all_times += times
            y = np.array([r["label"] for r in recs])
            thr = system.threshold(check)
            m = evaluate(y, p, thr, args.n_boot)
            m["throughput"] = latency_stats(times, bs)
            m["subsample"] = is_judge
            if check in ("prompt_injection", "grounded"):
                m["by_source"] = by_source(recs, p, thr)
            entry["checks"][check] = m
            for r, s in zip(recs, p, strict=True):
                preds.setdefault(r["id"], {"check": check, "label": r["label"]})[key] = float(s)
            print(f"   {check:17s} n={len(recs):5d} macroF1={m['macro_f1']:.4f} auroc={m['auroc']:.4f} "
                  f"ece={m['ece']:.4f}", flush=True)
            if check == "prompt_injection" and not is_judge:
                base_recall = m["recall"]
                for name, rs in robust_sets.items():
                    pr, _, _ = system.score(rs)
                    rec = float(np.mean(pr >= thr))
                    entry["robustness"][name] = {"n": len(rs), "recall": rec, "original_recall": base_recall,
                                                 "drop": base_recall - rec}
        # batch-1 latency on a fixed mixed sample of the checks this system supports
        if not is_judge:
            pool = [r for c in system.checks for r in test[c]]
            sample = [pool[i] for i in rng.choice(len(pool), min(LATENCY_N, len(pool)), replace=False)]
            entry["latency_batch1"] = batch1_latency(system, sample)
        else:
            entry["latency_batch1"] = latency_stats(all_times, 1)
            entry["prompt_tokens_mean"] = float(np.mean(system.prompt_tokens))
        results["systems"][key] = entry
        del system

    for key in args.latency_only:
        system = factories[key]()
        pool = [r for c in system.checks for r in test[c]]
        sample = [pool[i] for i in rng.choice(len(pool), min(LATENCY_N, len(pool)), replace=False)]
        results["systems"][key] = {**system.describe(), "latency_only": True,
                                   "latency_batch1": batch1_latency(system, sample)}
        # batch-16 throughput on the same sample
        _, times, bs = system.score(sample)
        results["systems"][key]["throughput"] = latency_stats(times, bs)
        print(f"== {system.name} latency {results['systems'][key]['latency_batch1']}", flush=True)
        del system

    # agreement and paired comparison between the fine-tuned model and the LLM judge subsample
    if "llm_judge" in results["systems"] and "laya_ft" in results["systems"]:
        comp = {}
        for check, recs in judge_sets.items():
            ids = [r["id"] for r in recs]
            y = np.array([preds[i]["label"] for i in ids])
            a = np.array([preds[i]["laya_ft"] for i in ids])
            b = np.array([preds[i]["llm_judge"] for i in ids])
            thr_a = results["systems"]["laya_ft"]["checks"][check]["threshold"]
            comp[check] = {
                "n": len(ids),
                "kappa": cohen_kappa((a >= thr_a).astype(int), (b >= 0.5).astype(int)),
                "laya_ft_on_subsample": point_metrics(y, a, thr_a),
                "auroc_delta_laya_minus_judge": paired_bootstrap_delta(
                    y, a, b, lambda yy, pp: point_metrics(yy, pp)["auroc"], seed=SEED),
            }
        results["laya_ft_vs_llm_judge"] = comp

    (out / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    with (out / "predictions.jsonl").open("w") as f:
        for i, row in sorted(preds.items()):
            f.write(json.dumps({"id": i, **row}) + "\n")
    from .report import write_report

    write_report(out)
    print(f"wrote {out}", flush=True)


if __name__ == "__main__":
    main()
