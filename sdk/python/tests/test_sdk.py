import calendar
import json

import httpx
import pytest

import verdict_guardrails as vg
from verdict_guardrails import (
    AsyncClient,
    AuthError,
    CheckResult,
    Client,
    InvalidRequest,
    RateLimitError,
    VerdictError,
    assert_checks,
    flag_rates,
)
from verdict_guardrails import client as client_mod

OK = {
    "id": "chk_1",
    "model_version": "m@1",
    "latency_ms": 12.5,
    "results": {
        "pii": {"flagged": True, "score": 0.97, "threshold": 0.63},
        "toxicity": {"flagged": False, "score": 0.02, "threshold": 0.53},
    },
}
ERR = {"error": {"code": "rate_limited", "message": "slow down"}}


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


def amake(handler, **kw):
    return AsyncClient(api_key="vk_x", base_url="https://api.test", transport=httpx.MockTransport(handler), **kw)


def batch_handler(sizes):
    def h(req):
        items = json.loads(req.read())["items"]
        sizes.append(len(items))
        return httpx.Response(200, json={"results": [OK] * len(items)})

    return h


# --- request / response -------------------------------------------------------------------------


def test_check_typed_result_and_request():
    seen = {}

    def h(req):
        seen["auth"], seen["body"], seen["ua"] = (
            req.headers["authorization"],
            json.loads(req.read()),
            req.headers["user-agent"],
        )
        return httpx.Response(200, json=OK)

    r = make(h).check("call 555", checks=["pii", "toxicity"], context="doc")
    assert seen["auth"] == "Bearer vk_x"
    assert seen["body"] == {"text": "call 555", "checks": ["pii", "toxicity"], "context": "doc"}
    assert seen["ua"] == f"verdict-guardrails/{vg.__version__}"
    assert r.id == "chk_1" and r["pii"].flagged and r.flagged == ["pii"] and r.results["toxicity"].score == 0.02


def test_check_omits_unset_fields():
    seen = {}

    def h(req):
        seen["body"] = json.loads(req.read())
        return httpx.Response(200, json=OK)

    make(h).check("hi")
    assert seen["body"] == {"text": "hi"}


def test_context_manager_closes():
    with make(lambda req: httpx.Response(200, json=OK)) as c:
        assert c.check("x").id == "chk_1"
    assert c._http.is_closed


def test_repr_hides_key():
    c = make(lambda req: httpx.Response(200, json=OK))
    assert "vk_x" not in repr(c) and "api.test" in repr(c)


# --- configuration ------------------------------------------------------------------------------


def test_api_key_required(monkeypatch):
    monkeypatch.delenv("VERDICT_API_KEY", raising=False)
    with pytest.raises(AuthError):
        Client()


def test_env_configuration(monkeypatch):
    monkeypatch.setenv("VERDICT_API_KEY", "vk_env")
    monkeypatch.setenv("VERDICT_BASE_URL", "https://env.test/")
    c = Client()
    assert c.api_key == "vk_env" and c.base_url == "https://env.test"
    monkeypatch.delenv("VERDICT_BASE_URL")
    assert Client().base_url == vg.DEFAULT_BASE_URL


def test_negative_retries_rejected():
    with pytest.raises(ValueError):
        Client(api_key="vk_x", max_retries=-1)


# --- retries and errors -------------------------------------------------------------------------


def test_retry_after_honoured(no_sleep):
    calls = []

    def h(req):
        calls.append(1)
        return (
            httpx.Response(429, headers={"Retry-After": "7"}, json=ERR)
            if len(calls) < 3
            else httpx.Response(200, json=OK)
        )

    assert make(h).check("x").id == "chk_1"
    assert no_sleep == [7.0, 7.0]


def test_backoff_on_503_then_gives_up(no_sleep):
    with pytest.raises(VerdictError) as e:
        make(lambda req: httpx.Response(503, json={"error": {"code": "busy", "message": "busy"}}), max_retries=2).check(
            "x"
        )
    assert e.value.status == 503 and len(no_sleep) == 2 and no_sleep[1] > 0


def test_rate_limit_error_after_retries():
    h = lambda req: httpx.Response(429, headers={"Retry-After": "3", "X-Request-ID": "r1"}, json=ERR)  # noqa: E731
    with pytest.raises(RateLimitError) as e:
        make(h, max_retries=1).check("x")
    assert e.value.retry_after == 3.0 and e.value.code == "rate_limited" and e.value.request_id == "r1"
    assert "HTTP 429" in str(e.value) and "request_id=r1" in str(e.value)


def test_long_retry_after_fails_fast(no_sleep):
    h = lambda req: httpx.Response(429, headers={"Retry-After": "3600"}, json=ERR)  # noqa: E731
    with pytest.raises(RateLimitError):
        make(h).check("x")
    assert not no_sleep


def test_no_retry_on_client_errors(no_sleep):
    n = []

    def h(req):
        n.append(1)
        return httpx.Response(401 if len(n) == 1 else 422, json=ERR)

    with pytest.raises(AuthError):
        make(h).check("x")
    with pytest.raises(InvalidRequest):
        make(h).check("x")
    assert len(n) == 2 and not no_sleep


def test_403_is_auth_error():
    with pytest.raises(AuthError):
        make(lambda req: httpx.Response(403, json=ERR)).check("x")


def test_500_not_retried(no_sleep):
    with pytest.raises(VerdictError) as e:
        make(lambda req: httpx.Response(500, text="boom")).check("x")
    assert e.value.status == 500 and e.value.message == "boom" and not no_sleep


def test_error_body_variants():
    with pytest.raises(InvalidRequest, match="Bad Request"):
        make(lambda req: httpx.Response(400, json={"error": {}})).check("x")
    with pytest.raises(InvalidRequest, match='"error"'):  # not an object: fall back to the raw body
        make(lambda req: httpx.Response(400, json={"error": "str"})).check("x")
    with pytest.raises(InvalidRequest) as e:
        make(lambda req: httpx.Response(400, json={"error": {"code": 7, "message": "m"}})).check("x")
    assert e.value.code == "7"
    assert str(VerdictError("plain")) == "plain"


def test_network_error_retried(no_sleep):
    n = []

    def h(req):
        n.append(1)
        if len(n) == 1:
            raise httpx.ConnectError("boom")
        return httpx.Response(200, json=OK)

    assert make(h).check("x").id == "chk_1" and len(no_sleep) == 1


def test_connect_error_gives_up():
    def h(req):
        raise httpx.ConnectError("down")

    with pytest.raises(VerdictError, match="network error") as e:
        make(h, max_retries=1).check("x")
    assert e.value.status is None


def test_timeout_and_other_transport_errors_not_retried(no_sleep):
    def timeout(req):
        raise httpx.ReadTimeout("slow")

    def reset(req):
        raise httpx.ReadError("reset")

    with pytest.raises(VerdictError, match="timed out"):
        make(timeout).check("x")
    with pytest.raises(VerdictError, match="network error"):
        make(reset).check("x")
    assert not no_sleep


def test_malformed_responses():
    with pytest.raises(VerdictError, match="non-JSON"):
        make(lambda req: httpx.Response(200, text="<html>")).check("x")
    with pytest.raises(VerdictError, match="unexpected response shape"):
        make(lambda req: httpx.Response(200, json={"id": "x"})).check("x")
    with pytest.raises(VerdictError, match="missing 'results'"):
        make(lambda req: httpx.Response(200, json=[])).check_batch([{"text": "x"}])


# --- retry-after parsing ------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value, expected",
    [
        (None, None),
        ("", None),
        ("5", 5.0),
        (" 2.5 ", 2.5),
        ("-3", 0.0),
        ("nan", None),
        ("inf", None),
        ("soon", None),
        ("Wed, 21 Oct 2026 07:28:10 GMT", 10.0),
        ("Wed, 21 Oct 2026 07:27:00 GMT", 0.0),
    ],
)
def test_parse_retry_after(value, expected):
    now = calendar.timegm((2026, 10, 21, 7, 28, 0))
    assert client_mod.parse_retry_after(value, now=now) == expected


def test_parse_retry_after_http_date_uses_wall_clock():
    assert client_mod.parse_retry_after("Wed, 21 Oct 2015 07:28:00 GMT") == 0.0


# --- batching -----------------------------------------------------------------------------------


def test_check_batch_validates_size():
    c = make(lambda req: httpx.Response(200, json={"results": []}))
    with pytest.raises(ValueError, match="at least one"):
        c.check_batch([])
    with pytest.raises(ValueError, match="at most 32"):
        c.check_batch([{"text": "x"}] * 33)


def test_check_many_splits_into_batches_of_32():
    sizes = []
    out = make(batch_handler(sizes)).check_many([f"t{i}" for i in range(70)], checks=["pii"], context="c")
    assert len(out) == 70 and sizes == [32, 32, 6]


# --- async --------------------------------------------------------------------------------------


async def test_async_client_retries_and_closes(no_sleep):
    n = []

    def h(req):
        n.append(1)
        return (
            httpx.Response(429, headers={"Retry-After": "1"}, json=ERR) if len(n) == 1 else httpx.Response(200, json=OK)
        )

    async with amake(h) as c:
        r = await c.check("x", checks=["pii"])
    assert r["pii"].flagged and no_sleep == [1.0] and c._http.is_closed


async def test_async_errors(no_sleep):
    with pytest.raises(AuthError):
        await amake(lambda req: httpx.Response(401, json=ERR)).check("x")
    with pytest.raises(VerdictError, match="non-JSON"):
        await amake(lambda req: httpx.Response(200, text="no")).check("x")
    with pytest.raises(RateLimitError):
        await amake(lambda req: httpx.Response(429, headers={"Retry-After": "9999"}, json=ERR)).check("x")
    assert not no_sleep


async def test_async_network_errors(no_sleep):
    n = []

    def flaky(req):
        n.append(1)
        if len(n) == 1:
            raise httpx.ConnectError("boom")
        return httpx.Response(200, json=OK)

    def down(req):
        raise httpx.ConnectError("down")

    def timeout(req):
        raise httpx.ReadTimeout("slow")

    assert (await amake(flaky).check("x")).id == "chk_1" and len(no_sleep) == 1
    with pytest.raises(VerdictError, match="network error"):
        await amake(down, max_retries=1).check("x")
    with pytest.raises(VerdictError, match="timed out"):
        await amake(timeout).check("x")


async def test_async_batches():
    sizes = []
    c = amake(batch_handler(sizes))
    assert len(await c.check_many([f"t{i}" for i in range(40)])) == 40
    assert sizes == [32, 8]
    assert len(await c.check_batch([{"text": "x"}])) == 1
    with pytest.raises(ValueError):
        await c.check_batch([])


# --- gate ---------------------------------------------------------------------------------------


def _result(flagged, check="pii"):
    return CheckResult.from_json({**OK, "results": {check: {"flagged": flagged, "score": 0.5, "threshold": 0.5}}})


def test_flag_rates_over_runs_of_each_check():
    rates = flag_rates([_result(True), _result(False), _result(True, "toxicity")])
    assert rates == {"pii": 0.5, "toxicity": 1.0}
    assert flag_rates([]) == {}


def test_assert_checks_gate():
    clean, leaky = _result(False), _result(True)
    assert assert_checks([clean, clean], max_rate={"pii": 0.0}) == {"pii": 0.0}
    assert assert_checks([clean, leaky], max_rate={"pii": 0.5})["pii"] == 0.5
    with pytest.raises(AssertionError, match=r"pii: 1/2 flagged \(50.0%\), max allowed 10.0%"):
        assert_checks([clean, leaky], max_rate={"pii": 0.1})
    with pytest.raises(AssertionError, match="no results ran"):
        assert_checks([clean], max_rate={"grounded": 0.0})
