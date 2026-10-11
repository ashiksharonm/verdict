"""Prompt injection / jailbreak attempts on user input.

Sources (all permissive):
- `deepset/prompt-injections` (Apache-2.0): short prompts, English and German, own train/test.
- `jackhhao/jailbreak-classification` (Apache-2.0): jailbreak vs benign prompts, own train/test.
- `reshabhs/SPML_Chatbot_Prompt_Injection` (MIT): user prompts written against chatbot system
  prompts; no official split, so a seeded group split is made here (the system prompt is not used).

Val is carved out of each source's training data; the sources' own test splits are the test set.
"""
from __future__ import annotations

from typing import Any

from .common import group_split, make_record

CHECK = "prompt_injection"


def _rows(texts, labels, source: str) -> list[dict[str, Any]]:
    out = []
    for text, label in zip(texts, labels, strict=True):
        if isinstance(text, str) and 3 <= len(text.strip()) <= 4000:
            out.append(make_record(CHECK, {"text": text.strip()}, int(label), source))
    return out


def build(seed: int, spml_cap: int = 6000) -> dict[str, list[dict[str, Any]]]:
    import pandas as pd
    from datasets import load_dataset
    from huggingface_hub import hf_hub_download

    out: dict[str, list[dict[str, Any]]] = {"train": [], "val": [], "test": []}

    deepset = load_dataset("deepset/prompt-injections")
    tr = _rows(deepset["train"]["text"], [int(x) for x in deepset["train"]["label"]], "deepset")
    out["test"] += _rows(deepset["test"]["text"], [int(x) for x in deepset["test"]["label"]], "deepset")

    jb = load_dataset("jackhhao/jailbreak-classification")
    tr += _rows(jb["train"]["prompt"], [t == "jailbreak" for t in jb["train"]["type"]], "jackhhao")
    out["test"] += _rows(jb["test"]["prompt"], [t == "jailbreak" for t in jb["test"]["type"]], "jackhhao")

    tv = group_split(tr, {"train": 0.85, "val": 0.15}, seed)
    out["train"] += tv["train"]
    out["val"] += tv["val"]

    path = hf_hub_download("reshabhs/SPML_Chatbot_Prompt_Injection", "spml_prompt_injection.csv",
                           repo_type="dataset")
    spml = pd.read_csv(path).sample(frac=1.0, random_state=seed).head(spml_cap)
    sp = group_split(_rows(spml["User Prompt"], spml["Prompt injection"], "spml"),
                     {"train": 0.75, "val": 0.1, "test": 0.15}, seed)
    for k in out:
        out[k] += sp[k]
    return out
