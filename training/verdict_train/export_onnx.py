"""Export a Laya checkpoint to ONNX (fp32) and int8 dynamic quantization, then check parity.

    python -m verdict_train.export_onnx --model artifacts/verdict-laya --out artifacts/onnx

The graph has the inputs and outputs `laya.onnx_agent.ONNXAgent` expects (`input_ids`,
`attention_mask`, `marker_pos`, `marker_mask`, `qtype` -> `logits`, `act_logits`), so the export
can also be served with Laya's own ONNX runtime. Parity is measured on the val split: decision
agreement at each check's tuned threshold and the max/mean absolute risk difference against the
PyTorch fp32 model. Results go to `training/manifests/onnx.json`.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import time
from pathlib import Path

import numpy as np

from .checks import CHECK_NAMES
from .data.common import read_jsonl
from .scoring import OnnxScorer, TorchScorer


def export(model_dir: str, out_dir: Path, opset: int = 17) -> Path:
    import torch

    scorer = TorchScorer(model_dir, device="cpu")
    model = scorer.model
    records = read_jsonl(Path("tests/fixtures/mini.jsonl"))[:4]
    batch = scorer.batch(scorer.items(records))
    args = (batch["input_ids"], batch["attention_mask"], batch["marker_pos"], batch["marker_mask"],
            batch["qtype"])
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "model.onnx"
    torch.onnx.export(
        model, args, str(path), opset_version=opset, dynamo=False,
        input_names=["input_ids", "attention_mask", "marker_pos", "marker_mask", "qtype"],
        output_names=["logits", "act_logits"],
        dynamic_axes={"input_ids": {0: "batch", 1: "seq"}, "attention_mask": {0: "batch", 1: "seq"},
                      "marker_pos": {0: "batch", 1: "options"}, "marker_mask": {0: "batch", 1: "options"},
                      "qtype": {0: "batch"}, "logits": {0: "batch", 1: "options"},
                      "act_logits": {0: "batch"}},
    )
    return path


def quantize(fp32: Path, out: Path) -> Path:
    from onnxruntime.quantization import QuantType, quantize_dynamic

    quantize_dynamic(str(fp32), str(out), weight_type=QuantType.QInt8, per_channel=True)
    return out


def _size_mb(path: Path) -> float:
    total = path.stat().st_size
    data = Path(str(path) + ".data")
    if data.exists():
        total += data.stat().st_size
    return round(total / 1e6, 1)


def parity_and_latency(model_dir: str, paths: dict[str, Path], data_dir: Path, threads: int,
                       n_latency: int = 200) -> dict:
    ref = TorchScorer(model_dir, device="cpu")
    report: dict = {"parity_split": "val", "cpu": platform.processor() or platform.machine(),
                    "ort_threads": threads, "variants": {}}
    val = {c: read_jsonl(data_dir / c / "val.jsonl") for c in CHECK_NAMES}
    ref_risk = {}
    for c, recs in val.items():
        z, _ = ref.logit_gaps(recs, batch_size=16)
        ref_risk[c] = ref.risk(recs, z)
    for name, path in paths.items():
        sc = OnnxScorer(model_dir, str(path), threads=threads)
        entry = {"size_mb": _size_mb(path), "checks": {}}
        for c, recs in val.items():
            z, _ = sc.logit_gaps(recs, batch_size=16)
            risk = sc.risk(recs, z)
            thr = sc.threshold(c)
            agree = float(np.mean((risk >= thr) == (ref_risk[c] >= thr)))
            diff = np.abs(risk - ref_risk[c])
            entry["checks"][c] = {"n": len(recs), "decision_agreement": agree,
                                  "max_abs_diff": float(diff.max()), "mean_abs_diff": float(diff.mean())}
        # single-request latency (batch 1) on a fixed mixed sample of val
        rng = np.random.default_rng(0)
        pool = [r for recs in val.values() for r in recs]
        sample = [pool[i] for i in rng.choice(len(pool), n_latency, replace=False)]
        sc.logit_gaps(sample[:5], batch_size=1)  # warm-up
        _, times = sc.logit_gaps(sample, batch_size=1, sort_by_length=False)
        from verdict_evals.metrics import latency_stats

        entry["latency_batch1"] = latency_stats(times)
        report["variants"][name] = entry
        print(name, json.dumps(entry)[:400], flush=True)
    return report


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--model", default="artifacts/verdict-laya")
    ap.add_argument("--out", default="artifacts/onnx")
    ap.add_argument("--data-dir", default="data/processed")
    ap.add_argument("--threads", type=int, default=os.cpu_count())
    ap.add_argument("--skip-export", action="store_true")
    ap.add_argument("--manifest", default="training/manifests/onnx.json")
    args = ap.parse_args()
    out = Path(args.out)
    fp32, int8 = out / "model.onnx", out / "model.int8.onnx"
    if not args.skip_export:
        t0 = time.time()
        export(args.model, out)
        quantize(fp32, int8)
        print(f"exported in {time.time() - t0:.0f}s", flush=True)
    report = parity_and_latency(args.model, {"onnx_fp32": fp32, "onnx_int8": int8}, Path(args.data_dir),
                                args.threads)
    Path(args.manifest).write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
