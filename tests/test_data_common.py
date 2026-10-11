import random

from verdict_train.data.common import (
    balanced_sample,
    dedup,
    finalize_splits,
    group_split,
    make_record,
    normalize,
    text_hash,
)
from verdict_train.data.pii import pii_entities, redact


def rec(text, label=0, group=None):
    return make_record("toxicity", {"text": text}, label, "unit", group)


def test_normalize_and_hash_ignore_case_and_whitespace():
    assert normalize("  Hello\n\tWORLD ") == "hello world"
    assert text_hash("Hello  world") == text_hash("hello world")


def test_dedup_keeps_first():
    rows = [rec("A b"), rec("a  B"), rec("c")]
    assert [r["state"]["text"] for r in dedup(rows)] == ["A b", "c"]


def test_group_split_is_seeded_and_disjoint():
    rows = [rec(f"t{i}", group=f"g{i % 10}") for i in range(100)]
    a = group_split(rows, {"train": 0.8, "val": 0.1, "test": 0.1}, seed=1)
    b = group_split(rows, {"train": 0.8, "val": 0.1, "test": 0.1}, seed=1)
    assert a == b
    groups = [{r["group"] for r in a[s]} for s in a]
    assert not (groups[0] & groups[1]) and not (groups[0] & groups[2]) and not (groups[1] & groups[2])
    assert sum(len(v) for v in a.values()) == 100


def test_finalize_removes_cross_split_leaks():
    shared = rec("leaked text", 1)
    splits = {"train": [shared, rec("only train")], "val": [rec("LEAKED  text", 1), rec("v")],
              "test": [rec("leaked text", 1), rec("t")]}
    out = finalize_splits(splits)
    assert [r["state"]["text"] for r in out["test"]] == ["leaked text", "t"]
    assert all(r["id"] != shared["id"] for r in out["val"] + out["train"])


def test_finalize_respects_groups():
    splits = {"train": [rec("x", group="ctx1"), rec("y", group="ctx2")], "val": [],
              "test": [rec("z", group="ctx1")]}
    assert [r["state"]["text"] for r in finalize_splits(splits)["train"]] == ["y"]


def test_balanced_sample_ratio_and_determinism():
    rows = [rec(f"p{i}", 1) for i in range(30)] + [rec(f"n{i}", 0) for i in range(100)]
    s = balanced_sample(rows, 40, seed=3)
    assert sum(r["label"] for r in s) == 20 and len(s) == 40
    assert s == balanced_sample(rows, 40, seed=3)
    # pool short of positives: fill from negatives
    s2 = balanced_sample(rows, 80, seed=3)
    assert len(s2) == 80 and sum(r["label"] for r in s2) == 30


def test_pii_redaction_removes_every_entity():
    ents = pii_entities([{"entity": "Urvashi Jaggi", "types": ["name"]},
                         {"entity": "Guernsey", "types": ["country"]},
                         {"entity": "u.j@example.com", "types": ["email"]}])
    assert ("Guernsey", "COUNTRY") not in ents and len(ents) == 2
    text = "Urvashi Jaggi (u.j@example.com) lives in Guernsey. Ms Jaggi agreed."
    out = redact(text, ents, random.Random(0))
    assert out is not None
    assert "Jaggi" not in out and "example.com" not in out and "Guernsey" in out
