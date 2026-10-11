"""Shared data utilities: normalisation, hashing, seeded splits, cross-split dedup, JSONL I/O."""
from __future__ import annotations

import hashlib
import json
import random
import re
import unicodedata
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

SPLITS = ("train", "val", "test")
_WS = re.compile(r"\s+")


def normalize(text: str) -> str:
    """Canonical form for duplicate detection: NFKC, case-folded, whitespace collapsed."""
    return _WS.sub(" ", unicodedata.normalize("NFKC", text)).strip().casefold()


def text_hash(text: str) -> str:
    return hashlib.sha256(normalize(text).encode("utf-8")).hexdigest()[:16]


def state_key(state: dict[str, str]) -> str:
    """Hash of the state's text fields, in a fixed key order."""
    return text_hash("\x1f".join(f"{k}={state[k]}" for k in sorted(state)))


def make_record(check: str, state: dict[str, str], label: int, source: str,
                group: str | None = None) -> dict[str, Any]:
    """A processed example. `group` keeps related rows (e.g. one RAG context) in one split."""
    key = state_key(state)
    return {"id": f"{check}-{key}", "check": check, "state": state, "label": int(label),
            "source": source, "group": group or key}


def dedup(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop exact (normalised) duplicates, keeping the first occurrence."""
    seen, out = set(), []
    for r in records:
        if r["id"] not in seen:
            seen.add(r["id"])
            out.append(r)
    return out


def drop_overlap(records: Sequence[dict[str, Any]], *held_out: Sequence[dict[str, Any]],
                 field: str = "id") -> list[dict[str, Any]]:
    """Records whose `field` (id or group) does not occur in any held-out split."""
    banned = {r[field] for split in held_out for r in split}
    return [r for r in records if r[field] not in banned]


def group_split(records: Sequence[dict[str, Any]], fractions: dict[str, float],
                seed: int) -> dict[str, list[dict[str, Any]]]:
    """Seeded split by `group`, so rows sharing a group never land in two splits."""
    groups = sorted({r["group"] for r in records})
    random.Random(seed).shuffle(groups)
    bounds, start = {}, 0
    names = list(fractions)
    for i, name in enumerate(names):
        end = len(groups) if i == len(names) - 1 else start + round(fractions[name] * len(groups))
        bounds.update({g: name for g in groups[start:end]})
        start = end
    out: dict[str, list[dict[str, Any]]] = {name: [] for name in names}
    for r in records:
        out[bounds[r["group"]]].append(r)
    return out


def balanced_sample(records: Sequence[dict[str, Any]], n: int, seed: int,
                    pos_frac: float | None = 0.5) -> list[dict[str, Any]]:
    """Seeded sample of up to `n` records.

    With `pos_frac` set, positives and negatives are drawn to that ratio (as far as the pool
    allows; the shortfall is filled from the other class). With `pos_frac=None` the pool's own
    class ratio is kept (a plain random sample).
    """
    rng = random.Random(seed)
    pool = list(records)
    if pos_frac is None:
        rng.shuffle(pool)
        return sorted(pool[:n], key=lambda r: r["id"])
    pos = [r for r in pool if r["label"] == 1]
    neg = [r for r in pool if r["label"] == 0]
    rng.shuffle(pos)
    rng.shuffle(neg)
    n_pos = min(len(pos), round(n * pos_frac))
    n_neg = min(len(neg), n - n_pos)
    n_pos = min(len(pos), n - n_neg)
    return sorted(pos[:n_pos] + neg[:n_neg], key=lambda r: r["id"])


def finalize_splits(splits: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    """Dedup within each split, then remove test items from val/train and val items from train.

    Overlap is checked on both the exact state (`id`) and the `group`.
    """
    test = dedup(splits["test"])
    val = drop_overlap(drop_overlap(dedup(splits["val"]), test), test, field="group")
    train = dedup(splits["train"])
    for held in (test, val):
        train = drop_overlap(drop_overlap(train, held), held, field="group")
    return {"train": train, "val": val, "test": test}


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> str:
    """Write rows and return the file's sha256."""
    path.parent.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha256()
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            line = json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
            f.write(line)
            h.update(line.encode("utf-8"))
    return h.hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with Path(path).open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def split_stats(records: Sequence[dict[str, Any]]) -> dict[str, Any]:
    by_source: dict[str, int] = {}
    for r in records:
        by_source[r["source"]] = by_source.get(r["source"], 0) + 1
    return {"n": len(records), "positives": sum(r["label"] for r in records),
            "by_source": dict(sorted(by_source.items()))}
