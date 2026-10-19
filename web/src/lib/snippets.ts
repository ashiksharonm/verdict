import { API_URL } from "./config";

export const SDK_INSTALL = `# Coming soon on PyPI: pip install verdict-guardrails
# Install from GitHub now:
pip install "git+https://github.com/ashiksharonm/verdict.git#subdirectory=sdk/python"`;

export const curlCheck = (key = "$VERDICT_API_KEY") => `curl -s ${API_URL}/v1/check \\
  -H "Authorization: Bearer ${key}" \\
  -H "Content-Type: application/json" \\
  -d '{"text": "Call me on +44 7700 900123", "checks": ["pii", "toxicity"]}'`;

export const pythonCheck = `from verdict_guardrails import Client

client = Client(api_key="vk_...")  # or set VERDICT_API_KEY
res = client.check("Call me on +44 7700 900123", checks=["pii", "toxicity"])
if res.results["pii"].flagged:
    ...  # mask or block`;

export const sampleResponse = `{
  "id": "chk_...",
  "model_version": "...",
  "results": {
    "pii":      { "flagged": true,  "score": 0.97, "threshold": 0.63 },
    "toxicity": { "flagged": false, "score": 0.04, "threshold": 0.53 }
  },
  "latency_ms": 787.4
}`;
