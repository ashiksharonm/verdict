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


def release_mps_cache_each_update(log_every: int = 25) -> None:
    """Empty the MPS allocator cache after every optimizer update.

    Batches have different sequence lengths, so on Apple GPUs the cached blocks fragment and
    "other allocations" grow until a 16 GB machine runs out of memory mid-epoch. Laya's trainer
    has no hook for this, so it goes on the global optimizer step.
    """
    import torch
    from torch.optim.optimizer import register_optimizer_step_post_hook

    if not torch.backends.mps.is_available():
        return
    updates = 0

    def hook(_optimizer, _args, _kwargs):
        nonlocal updates
        updates += 1
        torch.mps.empty_cache()
        if log_every and updates % log_every == 0:
            print(f"update {updates}: mps allocated {torch.mps.current_allocated_memory() / 2**30:.2f} GiB, "
                  f"driver {torch.mps.driver_allocated_memory() / 2**30:.2f} GiB", flush=True)

    register_optimizer_step_post_hook(hook)


def pad_batches_to_buckets(multiple: int = 64) -> None:
    """Pad every training batch's sequence length up to a multiple of `multiple`.

    MPS keeps a compiled graph per input shape, so with free-length batches driver memory still
    grows ~1 GiB per 25 updates even with the cache emptied. Buckets cap it at max_len/multiple
    shapes. Extra positions are padding with attention 0, so the model output is unchanged.
    """
    import laya.train as lt
    import torch

    collate = lt.collate_items

    def bucketed(batch, pad_id):
        res = collate(batch, pad_id)
        if res is None:
            return res
        n, length = res["input_ids"].shape
        extra = -length % multiple
        if extra:
            fill = {"input_ids": pad_id, "attention_mask": 0, "position_ids": 0, "option_ids": 0}
            for key, value in fill.items():
                if key in res:
                    res[key] = torch.cat([res[key], torch.full((n, extra), value, dtype=res[key].dtype)], dim=1)
        return res

    lt.collate_items = bucketed


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
    release_mps_cache_each_update()
    pad_batches_to_buckets()
    t0 = time.time()
    summary = finetune(str(train_path), base, cfg["out_dir"], tc, device=args.device)
    summary = {"base": cfg["base"], "data": data_info, "wall_hours": round((time.time() - t0) / 3600, 3),
               "laya_summary": summary}
    Path(cfg["out_dir"], "verdict_train_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print(f"done in {summary['wall_hours']} h", flush=True)


if __name__ == "__main__":
    main()
