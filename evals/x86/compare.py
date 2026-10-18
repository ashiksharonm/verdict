"""Metrics for x86 int8 scores next to the benchmark's fp32 and int8 (Apple M5) scores.

    python -m evals.x86.compare evals/results/2026-10-18-x86 --bench evals/results/2026-10-17

Uses the benchmark's metric code and per-check thresholds, on the same held-out items, and reports
decision agreement with the fp32 model, overall and split by CPU type (VNNI or not).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "evals"), str(ROOT / "training")]
from verdict_evals.metrics import bootstrap_ci, point_metrics  # noqa: E402

CHECKS = ["pii", "toxicity", "prompt_injection", "grounded"]


def _f1(m: dict) -> str:
    return f'{m["macro_f1"]:.3f} [{m["macro_f1_ci"][0]:.3f}, {m["macro_f1_ci"][1]:.3f}]'


def _pct(v: float | None) -> str:
    return "–" if v is None else f"{100 * v:.1f}%"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("x86_dir")
    ap.add_argument("--bench", default="evals/results/2026-10-17")
    ap.add_argument("--calibration", default="artifacts/verdict-laya/verdict_calibration.json")
    ap.add_argument("--n-boot", type=int, default=1000)
    ap.add_argument("--label", default="int8 reduce_range (x86)", help="name of the x86 variant in the report")
    args = ap.parse_args()

    bench = {r["id"]: r for r in map(json.loads, open(Path(args.bench) / "predictions.jsonl"))}
    x86 = {r["id"]: r for r in map(json.loads, open(Path(args.x86_dir) / "x86_predictions.jsonl"))}
    cal = json.load(open(args.calibration))
    thr = {c: float(cal["checks"][c]["threshold"]) if "checks" in cal else float(cal[c]["threshold"]) for c in CHECKS}

    out: dict = {"thresholds": thr, "checks": {}, "agreement_with_fp32": {}}
    for c in CHECKS:
        ids = [i for i, r in bench.items() if r["check"] == c and i in x86]
        y = [bench[i]["label"] for i in ids]
        row = {}
        for name, scores in (("fp32 (M5)", [bench[i]["laya_ft"] for i in ids]),
                             ("int8 (M5)", [bench[i]["laya_ft_int8"] for i in ids]),
                             (args.label, [x86[i]["score"] for i in ids])):
            m = point_metrics(y, scores, thr[c])
            ci = bootstrap_ci(y, scores, thr[c], n_boot=args.n_boot, seed=13, metrics=("macro_f1",))
            row[name] = {"n": len(ids), "macro_f1": m["macro_f1"], "macro_f1_ci": ci["macro_f1"], "auroc": m.get("auroc")}
        out["checks"][c] = row
        fp = np.array([bench[i]["laya_ft"] >= thr[c] for i in ids])
        new = np.array([x86[i]["score"] >= thr[c] for i in ids])
        vnni = np.array([bool(x86[i]["vnni"]) for i in ids], dtype=bool)
        out["agreement_with_fp32"][c] = {
            "all": float((fp == new).mean()),
            "vnni": float((fp[vnni] == new[vnni]).mean()) if vnni.any() else None,
            "no_vnni": float((fp[~vnni] == new[~vnni]).mean()) if (~vnni).any() else None,
            "n_vnni": int(vnni.sum()), "n_no_vnni": int((~vnni).sum()),
        }
    (Path(args.x86_dir) / "x86_metrics.json").write_text(json.dumps(out, indent=2))

    lines = [f"| check | fp32 (M5) | int8 (M5, published v1) | **{args.label}** | decisions = fp32 (x86: no-VNNI / VNNI) |",
             "|---|---|---|---|---|"]
    for c in CHECKS:
        r = out["checks"][c]
        a = out["agreement_with_fp32"][c]
        lines.append(f"| `{c}` (n={r['fp32 (M5)']['n']}) | {_f1(r['fp32 (M5)'])} | {_f1(r['int8 (M5)'])} | {_f1(r[args.label])} "
                     f"| {_pct(a['all'])} ({_pct(a['no_vnni'])} / {_pct(a['vnni'])}) |")
    md = "\n".join(lines)
    (Path(args.x86_dir) / "x86_report.md").write_text(md + "\n")
    print(md)


if __name__ == "__main__":
    main()
