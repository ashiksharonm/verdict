"""Build the processed train/val/test splits for every check.

    python -m verdict_train.prepare --config training/configs/data.yaml --out data/processed

Writes `<out>/<check>/<split>.jsonl` (gitignored) and a manifest with counts, class balance,
source mix and the sha256 of every file (`training/manifests/splits.json`, committed), so a
rebuild can be checked against the committed one.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from .data import builder
from .data.common import SPLITS, balanced_sample, finalize_splits, split_stats, write_jsonl


def prepare(config: dict, out: Path, checks: list[str] | None = None) -> dict:
    seed = int(config["seed"])
    manifest: dict = {"seed": seed, "checks": {}}
    for check, sizes in config["checks"].items():
        if checks and check not in checks:
            continue
        raw = builder(check).build(seed)
        pools = finalize_splits(raw)
        entry = {}
        for split in SPLITS:
            spec = sizes[split]
            rows = balanced_sample(pools[split], spec["n"], seed, spec.get("pos_frac"))
            digest = write_jsonl(out / check / f"{split}.jsonl", rows)
            entry[split] = {**split_stats(rows), "pool": len(pools[split]), "sha256": digest}
            print(f"{check:17s} {split:5s} n={len(rows):5d} pos={entry[split]['positives']:5d} "
                  f"pool={len(pools[split])}", flush=True)
        manifest["checks"][check] = entry
    return manifest


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", default="training/configs/data.yaml")
    ap.add_argument("--out", default="data/processed")
    ap.add_argument("--manifest", default="training/manifests/splits.json")
    ap.add_argument("--checks", nargs="*", help="subset of checks to rebuild")
    args = ap.parse_args()
    config = yaml.safe_load(Path(args.config).read_text())
    manifest = prepare(config, Path(args.out), args.checks)
    path = Path(args.manifest)
    if args.checks and path.exists():  # partial rebuild: keep the other checks' entries
        old = json.loads(path.read_text())
        old["checks"].update(manifest["checks"])
        manifest = old
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
