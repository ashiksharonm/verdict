import type { Metadata } from "next";
import DocLayout from "@/components/DocLayout";
import Code from "@/components/Code";
import { API_URL, CHECKS, CHECK_INFO } from "@/lib/config";
import { live, liveMs } from "@/lib/live";
import { PRESETS } from "@/lib/presets";
import { SDK_INSTALL, curlCheck, pythonCheck, sampleResponse } from "@/lib/snippets";

export const metadata: Metadata = { title: "Docs" };

const endpoints: [string, string, string][] = [
  ["POST", "/v1/check", "Run checks (API key). Body: text, checks, optional context."],
  ["POST", "/v1/playground/check", "Same, for the website. Requires header X-Turnstile-Token. Rate limited per IP."],
  ["GET", "/v1/checks", "List the available checks."],
  ["GET", "/healthz", "Liveness probe."],
  ["GET", "/readyz", "Readiness probe (model loaded)."],
  ["POST", "/v1/keys", "Create an API key. Body: name. The key is returned once."],
  ["GET", "/v1/keys", "List your keys (prefix only)."],
  ["DELETE", "/v1/keys/{id}", "Revoke a key."],
  ["GET", "/v1/usage", "Per-day counts, month total and monthly quota."],
];

const useCaseCode: Record<string, { py: string; curl: string }> = {
  "support-pii": {
    py: `res = client.check(reply, checks=["pii", "toxicity"])
if res.results["pii"].flagged:
    reply = "Sorry, I can't share that. A human agent will follow up."`,
    curl: `curl -s ${API_URL}/v1/check -H "Authorization: Bearer $VERDICT_API_KEY" -H "Content-Type: application/json" \\
  -d '{"text": "<bot reply>", "checks": ["pii", "toxicity"]}'`,
  },
  "rag-hallucination": {
    py: `res = client.check(answer, checks=["grounded"], context=retrieved_docs)
if res.results["grounded"].flagged:  # flagged = not supported by the context
    answer = "I couldn't verify this from the documents."`,
    curl: `curl -s ${API_URL}/v1/check -H "Authorization: Bearer $VERDICT_API_KEY" -H "Content-Type: application/json" \\
  -d '{"text": "<answer>", "context": "<retrieved docs>", "checks": ["grounded"]}'`,
  },
  "injection-firewall": {
    py: `if client.check(user_input, checks=["prompt_injection"]).results["prompt_injection"].flagged:
    return refuse()  # before the LLM is called`,
    curl: `curl -s ${API_URL}/v1/check -H "Authorization: Bearer $VERDICT_API_KEY" -H "Content-Type: application/json" \\
  -d '{"text": "<user input>", "checks": ["prompt_injection"]}'`,
  },
  "comment-moderation": {
    py: `r = client.check(comment, checks=["toxicity"]).results["toxicity"]
if r.score >= 0.8:
    hold_for_review(comment)
elif r.score >= 0.4:
    review_queue.add(comment)`,
    curl: `curl -s ${API_URL}/v1/check -H "Authorization: Bearer $VERDICT_API_KEY" -H "Content-Type: application/json" \\
  -d '{"text": "<comment>", "checks": ["toxicity"]}'`,
  },
  "ci-gate": {
    py: `# see "CI gate example" below`,
    curl: `# see "CI gate example" below`,
  },
  "cheap-prefilter": {
    py: `r = client.check(text, checks=["toxicity"]).results["toxicity"]
if 0.4 <= r.score <= 0.6:
    verdict = expensive_llm_judge(text)   # only uncertain cases
else:
    verdict = r.flagged`,
    curl: `curl -s ${API_URL}/v1/check -H "Authorization: Bearer $VERDICT_API_KEY" -H "Content-Type: application/json" \\
  -d '{"text": "<text>", "checks": ["toxicity"]}'`,
  },
};

const ciGate = `# .github/workflows/llm-quality.yml (excerpt)
- name: Verdict gate
  env:
    VERDICT_API_KEY: \${{ secrets.VERDICT_API_KEY }}
  run: python scripts/verdict_gate.py

# scripts/verdict_gate.py
import json, os, sys
import urllib.request

GOLDEN = json.load(open("tests/golden.json"))   # [{"answer": "...", "context": "..."}]
URL = "${API_URL}/v1/check"

def check(item):
    body = json.dumps({"text": item["answer"], "context": item["context"],
                       "checks": ["pii", "grounded"]}).encode()
    req = urllib.request.Request(URL, body, {
        "Authorization": "Bearer " + os.environ["VERDICT_API_KEY"],
        "Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req))["results"]

rows = [check(i) for i in GOLDEN]
pii = sum(r["pii"]["flagged"] for r in rows) / len(rows)
ungrounded = sum(r["grounded"]["flagged"] for r in rows) / len(rows)
print(f"pii rate {pii:.2%}, ungrounded rate {ungrounded:.2%}")
if pii > 0 or ungrounded > 0.05:
    sys.exit(1)`;

const TOC = [
  { id: "checks", label: "Checks" },
  { id: "api", label: "API reference" },
  { id: "quickstart", label: "Quickstart" },
  { id: "use-cases", label: "Use-case guides" },
  ...PRESETS.map((p) => ({ id: p.id, label: p.title, sub: true })),
  { id: "ci-gate", label: "CI gate example" },
];

export default function Page() {
  return (
    <DocLayout
      eyebrow="Documentation"
      title="Call the checks from your app"
      toc={TOC}
      intro={
        <>
          API base URL: <code>{API_URL}</code>. Authenticated endpoints take <code>Authorization: Bearer &lt;token&gt;</code>: an API key for <code>/v1/check</code>, a Supabase access token for key management.
        </>
      }
    >
      <h2 id="checks">Checks</h2>
      <ul>
        {CHECKS.map((c) => (
          <li key={c}><code>{c}</code>: {CHECK_INFO[c].question}</li>
        ))}
      </ul>
      <p>For <code>flagged</code>: <code>pii</code>, <code>toxicity</code> and <code>prompt_injection</code> flag when the text matches; <code>grounded</code> flags when the response is <em>not</em> supported by the context.</p>

      <h2 id="api">API reference</h2>
      <div className="tbl-wrap">
        <table className="tbl">
          <thead><tr><th>Method</th><th>Path</th><th>Description</th></tr></thead>
          <tbody>
            {endpoints.map(([m, p, d]) => (
              <tr key={m + p}><td><code>{m}</code></td><td><code>{p}</code></td><td className="whitespace-normal!">{d}</td></tr>
            ))}
          </tbody>
        </table>
      </div>

      <h3>POST /v1/check</h3>
      <p>Request:</p>
      <Code>{`{ "text": "string", "checks": ["pii", "grounded"], "context": "optional string" }`}</Code>
      <p>Response:</p>
      <Code>{sampleResponse}</Code>
      <p>Each result has <code>flagged</code> (score &gt;= threshold), the calibrated probability <code>score</code>, and the per-check <code>threshold</code>. <code>model_version</code> identifies the weights that produced the scores.</p>

      <h3>Keys and usage</h3>
      <Code>{`POST /v1/keys   {"name": "ci"}  ->  {"id", "key", "prefix", "name", "created_at"}   # key shown once
GET  /v1/keys
DELETE /v1/keys/{id}
GET  /v1/usage  ->  {"days": [{"day": "2026-10-17", "count": 12}], "month_total": 12, "quota": 10000, "keys": [...]}`}</Code>

      <h3>Rate limits and errors</h3>
      <p>
        HTTP 429 carries <code>Retry-After</code> (seconds) and <code>X-RateLimit-*</code> headers; wait that long before retrying. The hosted API scales to zero when idle. A cold request pays a model load of about {liveMs.loadS} s plus container start (measured {live.date}, {live.cold_start.note}), so it can be slow or return 502/503: retry with backoff. Warm requests take about {liveMs.p50} ms server-side p50 for 3 checks.
      </p>

      <h2 id="quickstart">Quickstart</h2>
      <Code label="curl">{curlCheck()}</Code>
      <p>Python SDK (not on PyPI yet):</p>
      <Code>{SDK_INSTALL}</Code>
      <Code>{pythonCheck}</Code>

      <h2 id="use-cases">Use-case guides</h2>
      <p>Each guide has a one-click preset in the <a href="/playground">playground</a>.</p>
      {PRESETS.map((p) => (
        <section key={p.id}>
          <h3 id={p.id}>{p.title}</h3>
          <p>{p.story}</p>
          <p>Decision: {p.decision}</p>
          <p>Checks: {p.checks.map((c) => <code key={c} className="mr-1">{c}</code>)}</p>
          <p>Python:</p>
          <Code>{useCaseCode[p.id].py}</Code>
          {p.id !== "ci-gate" && (<><p>curl:</p><Code>{useCaseCode[p.id].curl}</Code></>)}
        </section>
      ))}

      <h2 id="ci-gate">CI gate example</h2>
      <p>Run a golden set through the app and fail the pull request when PII or ungrounded answers go up. This version uses only the Python standard library against the HTTP API.</p>
      <Code>{ciGate}</Code>
    </DocLayout>
  );
}
