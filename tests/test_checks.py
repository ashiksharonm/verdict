import pytest
from verdict_train.checks import CHECKS, build_state, laya_row, risk_from_yes


def test_every_check_is_a_noul_question():
    for check in CHECKS.values():
        q = check.question()
        assert q["type"] == "noul" and "`" in q["instructions"]


def test_grounded_state_puts_response_first():
    state = build_state("grounded", context="ctx", response="resp")
    assert list(state) == ["response", "context"]
    with pytest.raises(ValueError):
        build_state("grounded", text="x")
    with pytest.raises(KeyError):
        build_state("nope", text="x")


def test_label_to_laya_answer_flips_for_grounded():
    tox = laya_row({"check": "toxicity", "state": {"text": "x"}, "label": 1})
    assert tox["expected"] == {"toxicity": True}
    ung = laya_row({"check": "grounded", "state": {"response": "r", "context": "c"}, "label": 1})
    assert ung["expected"] == {"grounded": False}
    assert risk_from_yes("grounded", 0.9) == pytest.approx(0.1)
    assert risk_from_yes("pii", 0.9) == pytest.approx(0.9)
