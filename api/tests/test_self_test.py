import pytest
import verdict_api.model as model_mod
from verdict_api.config import Settings
from verdict_api.model import ModelService, SelfTestError


class _ConstantScorer:
    """Stands in for an int8 graph that saturates on this CPU: every score is 0.5."""

    def __init__(self, *a, **kw):
        pass

    def logit_gaps(self, records, batch_size=16):
        return [0.0] * len(records), None

    def risk(self, records, z, calibrated=True):
        return [0.5] * len(records)

    def threshold(self, check):
        return 0.6


@pytest.fixture
def broken_model(monkeypatch, tmp_path):
    import verdict_train.scoring as scoring

    monkeypatch.setattr(scoring, "OnnxScorer", _ConstantScorer)
    return ModelService(Settings(model_dir=str(tmp_path), onnx_path=str(tmp_path / "m.onnx")))


def test_wrong_answers_refuse_to_serve(broken_model):
    with pytest.raises(SelfTestError):
        broken_model.load(strict=True)
    assert broken_model.ready is False
    assert "self-test failed" in broken_model.error


def test_non_strict_load_reports_on_readyz_instead_of_raising(broken_model):
    broken_model.load()
    assert broken_model.ready is False and broken_model.error


def test_self_test_covers_both_outcomes():
    assert {want for _, _, want in model_mod.SELF_TEST} == {True, False}
