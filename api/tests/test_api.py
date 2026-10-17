from conftest import add_key

BODY = {"text": "contact me at a@b.co"}


def test_meta_endpoints(client):
    assert client.get("/healthz").json()["status"] == "ok"
    r = client.get("/readyz")
    assert r.status_code == 200 and r.json()["model_version"] == "fake@test"
    names = [c["name"] for c in client.get("/v1/checks").json()["checks"]]
    assert names == ["pii", "toxicity", "prompt_injection", "grounded"]
    assert "verdict_http_requests_total" in client.get("/metrics").text
    assert "paths" in client.get("/openapi.json").json()


def test_request_id_echo_and_generated(client):
    assert client.get("/healthz", headers={"X-Request-ID": "abc-1"}).headers["x-request-id"] == "abc-1"
    assert len(client.get("/healthz", headers={"X-Request-ID": "bad id!"}).headers["x-request-id"]) == 32


def test_check_requires_key(client):
    r = client.post("/v1/check", json=BODY)
    assert r.status_code == 401 and r.json()["error"]["code"] == "missing_api_key"
    assert client.post("/v1/check", json=BODY, headers={"Authorization": "Bearer nope"}).status_code == 401
    assert client.post("/v1/check", json=BODY, headers={"Authorization": "Bearer vk_unknown"}).status_code == 401


def test_check_ok_defaults_and_headers(client, world, model):
    h = add_key(world)
    r = client.post("/v1/check", json=BODY, headers=h)
    assert r.status_code == 200
    d = r.json()
    assert set(d["results"]) == {"pii", "toxicity", "prompt_injection"}
    assert d["results"]["pii"] == {"flagged": True, "score": 0.9, "threshold": 0.5}
    assert d["results"]["toxicity"]["flagged"] is False
    assert d["model_version"] == "fake@test" and d["id"].startswith("chk_") and d["latency_ms"] >= 0
    assert r.headers["x-ratelimit-limit"] == "5" and r.headers["x-ratelimit-remaining"] == "4"


def test_grounded_needs_context(client, world):
    h = add_key(world)
    r = client.post("/v1/check", json={"text": "x", "checks": ["grounded"]}, headers=h)
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_request"
    ok = client.post("/v1/check", json={"text": "x", "checks": ["grounded"], "context": "c"}, headers=h)
    assert ok.status_code == 200 and list(ok.json()["results"]) == ["grounded"]


def test_validation_limits(client, world):
    h = add_key(world)
    assert client.post("/v1/check", json={"text": "x" * 20_001}, headers=h).status_code == 422
    assert client.post("/v1/check", json={"text": "x", "checks": ["bogus"]}, headers=h).status_code == 422
    assert client.post("/v1/check", json={"text": "x", "checks": []}, headers=h).status_code == 422
    assert client.post("/v1/check/batch", json={"items": [BODY] * 33}, headers=h).status_code == 422


def test_batch(client, world):
    h = add_key(world)
    r = client.post("/v1/check/batch", json={"items": [BODY, {"text": "you idiot", "checks": ["toxicity"]}]}, headers=h)
    assert r.status_code == 200
    res = r.json()["results"]
    assert res[0]["results"]["pii"]["flagged"] and res[1]["results"]["toxicity"]["flagged"]
    assert r.headers["x-ratelimit-remaining"] == "3"  # batch of 2 costs 2


def test_rate_limit_429(client, world):
    h = add_key(world)
    for _ in range(5):
        assert client.post("/v1/check", json=BODY, headers=h).status_code == 200
    r = client.post("/v1/check", json=BODY, headers=h)
    assert r.status_code == 429 and r.json()["error"]["code"] == "rate_limited"
    assert int(r.headers["retry-after"]) >= 1
    assert r.headers["x-ratelimit-remaining"] == "0" and r.headers["x-ratelimit-limit"] == "5"


def test_monthly_quota(client, world):
    h = add_key(world, quota=2)
    for _ in range(2):
        assert client.post("/v1/check", json={"text": f"t{_}"}, headers=h).status_code == 200
    r = client.post("/v1/check", json=BODY, headers=h)
    assert r.status_code == 429 and r.json()["error"]["code"] == "quota_exceeded" and "retry-after" in r.headers


def test_revoked_key_rejected(client, world):
    assert client.post("/v1/check", json=BODY, headers=add_key(world, revoked=True)).status_code == 401


def test_cache_hit_skips_model(client, world, model):
    h = add_key(world)
    client.post("/v1/check", json=BODY, headers=h)
    import time
    time.sleep(0.05)  # cache write is a background task
    client.post("/v1/check", json=BODY, headers=h)
    assert model.calls == 1
    assert not any("pii@b" in k for k in world.redis)  # keys are hashes, no payload text


def test_redis_down_fails_open_for_keys(client, world):
    h = add_key(world)
    world.redis_down = True
    r = client.post("/v1/check", json=BODY, headers=h)
    assert r.status_code == 200 and "x-ratelimit-limit" not in r.headers


def test_no_tables_gives_503_but_playground_works(client, world):
    world.tables_exist = False
    r = client.post("/v1/check", json=BODY, headers={"Authorization": "Bearer vk_x"})
    assert r.status_code == 503 and r.json()["error"]["code"] == "key_store_unavailable"
    r = client.get("/v1/keys", headers={"Authorization": "Bearer jwt-alice"})
    assert r.status_code == 503 and r.json()["error"]["code"] == "database_unavailable"
    ok = client.post("/v1/playground/check", json=BODY, headers={"X-Turnstile-Token": "tok"})
    assert ok.status_code == 200


def test_model_not_ready(client, model, world):
    model.ready = False
    r = client.post("/v1/check", json=BODY, headers=add_key(world))
    assert r.status_code == 503 and r.json()["error"]["code"] == "model_loading"
    assert client.get("/readyz").status_code == 503


# ------------------------------------------------------------------ playground
def test_playground_requires_token(client):
    r = client.post("/v1/playground/check", json=BODY)
    assert r.status_code == 400 and r.json()["error"]["code"] == "missing_turnstile_token"


def test_playground_turnstile_rejected(client, world):
    world.turnstile_ok = False
    r = client.post("/v1/playground/check", json=BODY, headers={"X-Turnstile-Token": "bad"})
    assert r.status_code == 403


def test_playground_ip_limit(client):
    h = {"X-Turnstile-Token": "t", "X-Forwarded-For": "1.2.3.4"}
    assert [client.post("/v1/playground/check", json=BODY, headers=h).status_code for _ in range(3)] == [200] * 3
    r = client.post("/v1/playground/check", json=BODY, headers=h)
    assert r.status_code == 429 and "retry-after" in r.headers
    other = {"X-Turnstile-Token": "t", "X-Forwarded-For": "5.6.7.8"}
    assert client.post("/v1/playground/check", json=BODY, headers=other).status_code == 200


def test_playground_fails_closed_without_redis(client, world):
    world.redis_down = True
    r = client.post("/v1/playground/check", json=BODY, headers={"X-Turnstile-Token": "t"})
    assert r.status_code == 503


# ------------------------------------------------------------------ keys
def test_key_lifecycle(client, world):
    jwt = {"Authorization": "Bearer jwt-alice"}
    assert client.post("/v1/keys", json={"name": "ci"}).status_code == 401
    assert client.post("/v1/keys", json={"name": "ci"}, headers={"Authorization": "Bearer jwt-evil"}).status_code == 401
    r = client.post("/v1/keys", json={"name": "ci"}, headers=jwt)
    assert r.status_code == 201
    created = r.json()
    assert created["key"].startswith("vk_") and created["prefix"] == created["key"][:10]
    assert created["key"] not in str(world.api_keys)  # only the hash is stored
    listed = client.get("/v1/keys", headers=jwt).json()["keys"]
    assert len(listed) == 1 and "key" not in listed[0] and "key_hash" not in listed[0]
    assert client.get("/v1/keys", headers={"Authorization": "Bearer jwt-bob"}).json()["keys"] == []
    # the new key authenticates; revoking by another user fails; revoking by the owner works
    api = {"Authorization": f"Bearer {created['key']}"}
    assert client.post("/v1/check", json=BODY, headers=api).status_code == 200
    kid = created["id"]
    assert client.delete(f"/v1/keys/{kid}", headers={"Authorization": "Bearer jwt-bob"}).status_code == 404
    assert client.delete(f"/v1/keys/{kid}", headers=jwt).status_code == 204
    assert client.post("/v1/check", json=BODY, headers=api).status_code == 401
    assert client.delete(f"/v1/keys/{kid}", headers=jwt).status_code == 404


def test_usage(client, world):
    jwt = {"Authorization": "Bearer jwt-alice"}
    created = client.post("/v1/keys", json={"name": "ci"}, headers=jwt).json()
    api = {"Authorization": f"Bearer {created['key']}"}
    for _ in range(3):
        client.post("/v1/check", json=BODY, headers=api)
    import time
    time.sleep(0.1)
    u = client.get("/v1/usage", headers=jwt).json()
    assert u["month_total"] == 3 and u["quota"] == 8
    assert sum(d["count"] for d in u["days"]) == 3 and u["keys"][0]["month_count"] == 3


def test_key_limit(client):
    jwt = {"Authorization": "Bearer jwt-alice"}
    codes = [client.post("/v1/keys", json={"name": f"k{i}"}, headers=jwt).status_code for i in range(6)]
    assert codes == [201] * 5 + [409]


def test_cors(client):
    for origin, ok in [("http://localhost:3000", True), ("https://my-app-git-x.vercel.app", True),
                       ("https://evil.example.com", False), ("https://x.vercel.app.evil.com", False)]:
        r = client.options("/v1/check", headers={"Origin": origin, "Access-Control-Request-Method": "POST"})
        assert (r.headers.get("access-control-allow-origin") == origin) is ok


def test_flush_usage_to_db(client, world):
    h = add_key(world)
    client.post("/v1/check", json=BODY, headers=h)
    import time
    time.sleep(0.05)
    import asyncio
    ks = client.app.state.keystore
    asyncio.run(ks.flush())  # fake http client has no loop affinity
    assert world.usage_daily and world.usage_daily[0]["count"] == 1
