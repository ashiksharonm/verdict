"""Toxicity: `google/civil_comments` (CC0-1.0).

A comment is toxic when its crowd-rated `toxicity` score is >= 0.5 (the dataset's own convention).
Train and val come from the `train` split (seeded group split), test from the `test` split. The
pools are pre-sampled per class so the 1.8M-row train split is not carried around in memory.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from .common import group_split, make_record

CHECK = "toxicity"
THRESHOLD = 0.5


def records(df: pd.DataFrame, per_class: int, seed: int, source: str) -> list[dict[str, Any]]:
    df = df[df["text"].str.len().between(20, 1500)]
    tox = df[df["toxicity"] >= THRESHOLD]
    non = df[df["toxicity"] < THRESHOLD]
    parts = [x.sample(n=min(per_class, len(x)), random_state=seed) for x in (tox, non)]
    out = []
    for part in parts:
        for text, score in zip(part["text"], part["toxicity"], strict=True):
            out.append(make_record(CHECK, {"text": text}, int(score >= THRESHOLD), source))
    return out


def build(seed: int, pool_per_class: int = 6000) -> dict[str, list[dict[str, Any]]]:
    from datasets import load_dataset

    ds = load_dataset("google/civil_comments", columns=["text", "toxicity"])
    train_pool = records(ds["train"].to_pandas(), pool_per_class, seed, "civil_comments")
    tv = group_split(train_pool, {"train": 0.9, "val": 0.1}, seed)
    test = records(ds["test"].to_pandas(), 2000, seed, "civil_comments")
    return {"train": tv["train"], "val": tv["val"], "test": test}
