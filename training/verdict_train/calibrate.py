"""Per-check temperature scaling and decision thresholds, fitted on the val split only.

    python -m verdict_train.calibrate --model artifacts/verdict-laya --device mps

For each check: score val, fit one temperature `T` minimising NLL of `sigmoid(z / T)`, then pick
the threshold on the calibrated risk that maximises val macro-F1. The result is written into the
checkpoint directory (`verdict_calibration.json`, read by the scorers and the API) and copied to
`training/manifests/calibration.json` so the committed numbers match the artifact.
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import numpy as np

from .checks import CHECK_NAMES
from .data.common import read_jsonl
from .scoring import TorchScorer, fit_temperature, sigmoid, yes_labels


def calibrate(model_dir: str, data_dir: Path, device: str, max_len: int | None = None) -> dict:
    from verdict_evals.metrics import best_threshold, point_metrics

    scorer = TorchScorer(model_dir, device=device, max_len=max_len)
    out = {"model_dir": str(model_dir), "max_len": scorer.max_len, "split": "val", "checks": {}}
    for check in CHECK_NAMES:
        records = read_jsonl(data_dir / check / "val.jsonl")
        z, _ = scorer.logit_gaps(records)
        y_yes = yes_labels(records)
        y = np.array([r["label"] for r in records])
        t = fit_temperature(z, y_yes)
        before = scorer.risk(records, z, calibrated=False)
        p_yes = sigmoid(z / t)
        risk = p_yes if check != "grounded" else 1 - p_yes
        thr = best_threshold(y, risk)
        out["checks"][check] = {
            "n": len(records), "temperature": t, "threshold": thr,
            "val_uncalibrated": point_metrics(y, before, 0.5),
            "val_calibrated": point_metrics(y, risk, thr),
        }
        m = out["checks"][check]
        print(f"{check:17s} T={t:.3f} thr={thr:.3f} ECE {m['val_uncalibrated']['ece']:.4f}->"
              f"{m['val_calibrated']['ece']:.4f} macroF1 {m['val_calibrated']['macro_f1']:.4f}", flush=True)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--model", default="artifacts/verdict-laya")
    ap.add_argument("--data-dir", default="data/processed")
    ap.add_argument("--device", default="mps")
    ap.add_argument("--max-len", type=int, default=None)
    ap.add_argument("--manifest", default="training/manifests/calibration.json")
    args = ap.parse_args()
    result = calibrate(args.model, Path(args.data_dir), args.device, args.max_len)
    path = Path(args.model) / "verdict_calibration.json"
    path.write_text(json.dumps(result, indent=2) + "\n")
    Path(args.manifest).parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(path, args.manifest)


if __name__ == "__main__":
    main()
