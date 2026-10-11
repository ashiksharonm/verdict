"""Groundedness: is a RAG response supported by its context?

Source: `wandb/RAGTruth-processed`, a processed copy of RAGTruth (Niu et al., 2024; MIT), with
word-level hallucination annotations on responses from several LLMs across QA, summarisation and
data-to-text. A response is **not grounded** (label 1) when it has at least one annotated
`evident_conflict` or `baseless_info` span.

The query/instruction is prefixed to the context, since a QA answer is judged against both.
Train/val are a group split of the `train` split by context, so all responses written for one
context stay together; RAGTruth's own `test` split (no shared contexts with train) is the test set.
"""
from __future__ import annotations

from typing import Any

from .common import group_split, make_record, text_hash

CHECK = "grounded"


def records(rows) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        h = row["hallucination_labels_processed"]
        label = int((h["evident_conflict"] + h["baseless_info"]) > 0)
        context = f"{row['query'].strip()}\n\n{row['context'].strip()}"
        response = row["output"].strip()
        if not response:
            continue
        state = {"response": response, "context": context}
        out.append(make_record(CHECK, state, label, f"ragtruth-{row['task_type'].lower()}",
                               group=f"ctx:{text_hash(context)}"))
    return out


def build(seed: int) -> dict[str, list[dict[str, Any]]]:
    from datasets import load_dataset

    ds = load_dataset("wandb/RAGTruth-processed")
    tv = group_split(records(ds["train"]), {"train": 0.9, "val": 0.1}, seed)
    return {"train": tv["train"], "val": tv["val"], "test": records(ds["test"])}
