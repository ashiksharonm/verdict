"""End-to-end smoke run of the benchmark harness on the hand-written fixture (no downloads)."""
import json
import sys

from verdict_evals import run


def test_fixture_smoke_eval(tmp_path, monkeypatch):
    argv = ["run", "--fixture", "--systems", "tfidf", "keyword", "--latency-only", "--n-boot", "50",
            "--out", str(tmp_path)]
    monkeypatch.setattr(sys, "argv", argv)
    run.main()
    res = json.loads((tmp_path / "results.json").read_text())
    assert res["fixture"] is True
    assert set(res["systems"]) == {"tfidf", "keyword"}
    tox = res["systems"]["keyword"]["checks"]["toxicity"]
    assert tox["n"] == 8 and 0.0 <= tox["macro_f1"] <= 1.0 and "ci95" in tox
    assert set(res["systems"]["keyword"]["robustness"]) == {"leetspeak", "homoglyphs", "zero_width",
                                                            "random_case", "base64"}
    report = (tmp_path / "report.md").read_text()
    assert "Fixture smoke run" in report and "| keyword/regex |" in report
    lines = (tmp_path / "predictions.jsonl").read_text().splitlines()
    assert len(lines) == 32
