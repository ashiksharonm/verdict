"""Fine-tune one multi-check Laya model with `laya.train.finetune`.

    python -m verdict_train.finetune --config training/configs/train.yaml

Every check is one typed `noul` question (see `checks.py`); rows from all checks are mixed into
one training file. Laya's own trainer handles encoding, the loss, a held-out calibration slice and
checkpointing; Verdict's per-check temperatures and thresholds are fitted afterwards on the val
split by `verdict_train.calibrate`.
"""
from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path

import yaml

from .checks import laya_row
from .data.common import read_jsonl, write_jsonl


def build_files(cfg: dict) -> tuple[Path, Path, dict]:
    data_dir, out = Path(cfg["data_dir"]), Path(cfg["out_dir"])
    rng = random.Random(cfg["seed"])
    train, val, counts = [], [], {}
    for check, cap in cfg["train_per_check"].items():
        rows = read_jsonl(data_dir / check / "train.jsonl")
        if cap and len(rows) > cap:
            rows = rng.sample(rows, cap)
        train += [laya_row(r) for r in rows]
        val += [laya_row(r) for r in read_jsonl(data_dir / check / "val.jsonl")]
        counts[check] = {"train": len(rows), "train_positives": sum(r["label"] for r in rows)}
    rng.shuffle(train)
    train_path, val_path = out / "train_laya.jsonl", out / "val_laya.jsonl"
    hashes = {"train_sha256": write_jsonl(train_path, train), "val_sha256": write_jsonl(val_path, val)}
    return train_path, val_path, {"per_check": counts, **hashes}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", default="training/configs/train.yaml")
    ap.add_argument("--device", default="auto")
    ap.add_argument("--dry-run", action="store_true", help="build files and print the update budget only")
    args = ap.parse_args()
    cfg = yaml.safe_load(Path(args.config).read_text())

    from laya.train import TrainConfig, dry_run, finetune, resolve_checkpoint_dir

    train_path, val_path, data_info = build_files(cfg)
    tc = TrainConfig(seed=cfg["seed"], max_len=cfg["max_len"], eval_data=str(val_path), **cfg["laya"])
    base = resolve_checkpoint_dir(cfg["base"])
    if args.dry_run:
        print(json.dumps(dry_run(str(train_path), base, tc), indent=2, default=str))
        return
    t0 = time.time()
    summary = finetune(str(train_path), base, cfg["out_dir"], tc, device=args.device)
    summary = {"base": cfg["base"], "data": data_info, "wall_hours": round((time.time() - t0) / 3600, 3),
               "laya_summary": summary}
    Path(cfg["out_dir"], "verdict_train_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print(f"done in {summary['wall_hours']} h", flush=True)


if __name__ == "__main__":
    main()
