import httpx
import pytest
import verdict
from verdict import AsyncClient, AuthError, Client, InvalidRequest, RateLimitError, assert_checks
from verdict import client as client_mod

OK = {"id": "chk_1", "model_version": "m@1", "latency_ms": 12.5,
      "results": {"pii": {"flagged": True, "score": 0.97, "threshold": 0.63},
                  "toxicity": {"flagged": False, "score": 0.02, "threshold": 0.53}}}


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    slept = []
    monkeypatch.setattr(client_mod.time, "sleep", slept.append)

    async def asleep(s):
        slept.append(s)

    monkeypatch.setattr(client_mod.asyncio, "sleep", asleep)
    return slept


def make(handler, **kw):
    return Client(api_key="vk_x", base_url="https://api.test", transport=httpx.MockTransport(handler), **kw)


def test_check_typed_result_and_request():
    seen = {}

    def h(req):
        seen["auth"], seen["body"] = req.headers["authorization"], req.read()
        return httpx.Response(200, json=OK)

    r = make(h).check("call 555", checks=["pii", "toxicity"])
    assert seen["auth"] == "Bearer vk_x" and b'"checks"' in seen["body"] and b"context" not in seen["body"]
    assert r.id == "chk_1" and r["pii"].flagged and r.flagged == ["pii"] and r.results["toxicity"].score == 0.02


def test_retry_after_honoured(no_sleep):
    calls = []

    def h(req):
        calls.append(1)
        return httpx.Response(429, headers={"Retry-After": "7"}, json={"error": {"code": "rate_limited", "message": "slow"}}) \
            if len(calls) < 3 else httpx.Response(200, json=OK)

    assert make(h).check("x").id == "chk_1"
    assert no_sleep == [7.0, 7.0]


def test_backoff_on_503_then_gives_up(no_sleep):
    def h(req):
        return httpx.Response(503, json={"error": {"code": "busy", "message": "busy"}})

    with pytest.raises(verdict.VerdictError):
        make(h, max_retries=2).check("x")
    assert len(no_sleep) == 2 and no_sleep[1] > 0


def test_rate_limit_error_after_retries():
    def h(req):
        return httpx.Response(429, headers={"Retry-After": "3"}, json={"error": {"code": "quota_exceeded", "message": "q"}})

    with pytest.raises(RateLimitError) as e:
        make(h, max_retries=1).check("x")
    assert e.value.retry_after == 3.0 and e.value.code == "quota_exceeded"


def test_no_retry_on_client_errors(no_sleep):
    n = []

    def h(req):
        n.append(1)
        return httpx.Response(401 if len(n) == 1 else 422, json={"error": {"code": "c", "message": "m"}})

    with pytest.raises(AuthError):
        make(h).check("x")
    with pytest.raises(InvalidRequest):
        make(h).check("x")
    assert len(n) == 2 and not no_sleep


def test_network_error_retried(no_sleep):
    n = []

    def h(req):
        n.append(1)
        if len(n) == 1:
            raise httpx.ConnectError("boom")
        return httpx.Response(200, json=OK)

    assert make(h).check("x").id == "chk_1" and len(no_sleep) == 1


def test_check_many_splits_into_batches_of_32():
    sizes = []

    def h(req):
        import json
        items = json.loads(req.read())["items"]
        sizes.append(len(items))
        return httpx.Response(200, json={"results": [OK] * len(items)})

    assert len(make(h).check_many([f"t{i}" for i in range(70)])) == 70
    assert sizes == [32, 32, 6]


def test_api_key_required(monkeypatch):
    monkeypatch.delenv("VERDICT_API_KEY", raising=False)
    with pytest.raises(AuthError):
        Client()


async def test_async_client(no_sleep):
    n = []

    def h(req):
        n.append(1)
        return httpx.Response(429, headers={"Retry-After": "1"}, json={}) if len(n) == 1 else httpx.Response(200, json=OK)

    async with AsyncClient(api_key="vk_x", base_url="https://api.test", transport=httpx.MockTransport(h)) as c:
        r = await c.check("x", checks=["pii"])
    assert r["pii"].flagged and no_sleep == [1.0]


def test_assert_checks_gate():
    from verdict.models import CheckResult
    clean = CheckResult.from_json({**OK, "results": {"pii": {"flagged": False, "score": 0.1, "threshold": 0.5}}})
    leaky = CheckResult.from_json(OK)
    assert assert_checks([clean, clean], max_rate={"pii": 0.0}) == {"pii": 0.0}
    assert assert_checks([clean, leaky], max_rate={"pii": 0.5})["pii"] == 0.5
    with pytest.raises(AssertionError, match="pii: flagged rate 0.500"):
        assert_checks([clean, leaky], max_rate={"pii": 0.1})
    with pytest.raises(AssertionError, match="no results ran"):
        assert_checks([clean], max_rate={"grounded": 0.0})
