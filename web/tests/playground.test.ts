import { describe, expect, it, vi } from "vitest";
import { backoffMs, parseRetryAfter, playgroundCheck } from "@/lib/api";

const okBody = {
  id: "chk_1",
  model_version: "v-test",
  results: { pii: { flagged: true, score: 0.97, threshold: 0.63 } },
  latency_ms: 12.5,
};
const json = (status: number, body: unknown, headers: Record<string, string> = {}) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json", ...headers } });
const req = { text: "call me", checks: ["pii"] };
const base = { baseUrl: "https://api.test", sleep: async () => {} };

describe("playgroundCheck", () => {
  it("posts to /v1/playground/check with the Turnstile header and parses the result", async () => {
    const f = vi.fn().mockResolvedValue(json(200, okBody));
    const out = await playgroundCheck({ ...req, context: "ctx" }, { ...base, token: "tok", fetchImpl: f });
    expect(out).toEqual({ kind: "ok", data: okBody, attempts: 1 });
    const [url, init] = f.mock.calls[0];
    expect(url).toBe("https://api.test/v1/playground/check");
    expect(init.headers["X-Turnstile-Token"]).toBe("tok");
    expect(JSON.parse(init.body)).toEqual({ text: "call me", checks: ["pii"], context: "ctx" });
  });

  it("returns rate_limited with Retry-After on 429 and does not retry", async () => {
    const f = vi.fn().mockResolvedValue(json(429, { detail: "slow down" }, { "Retry-After": "17" }));
    const out = await playgroundCheck(req, { ...base, fetchImpl: f });
    expect(out).toMatchObject({ kind: "rate_limited", retryAfter: 17 });
    expect(f).toHaveBeenCalledTimes(1);
  });

  it("retries with backoff while the API is asleep, then succeeds", async () => {
    const f = vi
      .fn()
      .mockResolvedValueOnce(new Response("<html>starting</html>", { status: 503 }))
      .mockRejectedValueOnce(new TypeError("fetch failed"))
      .mockResolvedValueOnce(json(200, okBody));
    const warming = vi.fn();
    const out = await playgroundCheck(req, { ...base, fetchImpl: f, onWarming: warming });
    expect(out).toMatchObject({ kind: "ok", attempts: 3 });
    expect(warming).toHaveBeenCalledTimes(2);
    expect(warming.mock.calls[0][0].waitMs).toBe(backoffMs(1));
  });

  it("gives up after about 60 s of cold-start retries", async () => {
    let t = 0;
    const f = vi.fn().mockResolvedValue(new Response("", { status: 503 }));
    const out = await playgroundCheck(req, { ...base, fetchImpl: f, now: () => t, sleep: async (ms) => void (t += ms) });
    expect(out.kind).toBe("error");
    expect(t).toBeLessThanOrEqual(60_000);
    expect(f.mock.calls.length).toBeGreaterThan(4);
  });

  it("surfaces validation errors without retrying", async () => {
    const f = vi.fn().mockResolvedValue(json(403, { detail: "Turnstile verification failed" }));
    const out = await playgroundCheck(req, { ...base, fetchImpl: f });
    expect(out).toEqual({ kind: "error", status: 403, message: "Turnstile verification failed" });
    expect(f).toHaveBeenCalledTimes(1);
  });

  it("parses Retry-After values", () => {
    expect(parseRetryAfter("5")).toBe(5);
    expect(parseRetryAfter(null)).toBeNull();
    expect(parseRetryAfter("nonsense")).toBeNull();
  });
});
