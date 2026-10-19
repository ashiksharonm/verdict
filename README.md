# Verdict

Calibrated guardrails and evals for LLM apps, from one small model you can self-host for free. Verdict fine-tunes [Laya](https://huggingface.co/convaiinnovations/laya)
(a ModernBERT-large decision model that answers typed questions with probabilities in one forward pass)
into a single multi-check model for:

| check | question |
|---|---|
| `pii` | Does the text contain personal data? |
| `toxicity` | Is the text toxic, insulting or threatening? |
| `prompt_injection` | Is this user input an injection or jailbreak attempt? |
| `grounded` | Is the response supported by the provided context? |

**Live:** [website and playground](https://verdict-sooty-zeta.vercel.app) ·
[API](https://ashiksharonm--verdict-api.us-east.modal.run/docs) ([reference](docs/API.md)) ·
[model on Hugging Face](https://huggingface.co/ashiksharon005/verdict-laya) (Apache-2.0)

## Quickstart

Create a free API key on the [dashboard](https://verdict-sooty-zeta.vercel.app/dashboard), then:

```bash
curl -s https://ashiksharonm--verdict-api.us-east.modal.run/v1/check \
  -H "Authorization: Bearer $VERDICT_API_KEY" -H "Content-Type: application/json" \
  -d '{"text": "Call me on +44 7700 900123", "checks": ["pii", "toxicity"]}'
```

```json
{"id": "chk_f18d663ebba944b6", "model_version": "verdict-laya@5a21230f-fp32",
 "results": {"pii": {"flagged": true, "score": 0.9996, "threshold": 0.63},
             "toxicity": {"flagged": false, "score": 0.0167, "threshold": 0.53}},
 "latency_ms": 668.76}
```

(Real response from the live API on 2026-10-19, scores rounded to four places.)

Every score is a calibrated probability; `flagged` applies a per-check threshold chosen on validation
data. For `grounded`, pass the source in `context`; flagged means the response is *not* supported.
Free keys get 60 requests/min and 10,000 checks/month.

## Production numbers

Measured against the live API on 2026-10-18 ([`live.json`](evals/results/2026-10-18-live/live.json),
[log](evals/results/2026-10-18-live/e2e.log), [script](evals/x86/e2e_live.py)): end-to-end checks
21/21 passed; three default checks take **959 ms server-side (p50, 997 ms p95)** on Modal's
4-vCPU CPU, 1.74 s round trip from India to us-east. After 2 minutes idle the API scales to zero;
the next request waits for a container start plus a 12 s model load and self-test.

The API serves the **fp32** ONNX graph. On Modal's x86 CPUs it reproduces the benchmark exactly:
100% of decisions on all 6,449 held-out items match ([report](evals/results/2026-10-18-x86-fp32/x86_report.md)).
The int8 export is for Apple silicon only: on x86 CPUs without VNNI its u8s8 products saturate and
every score collapses to about 0.5, and re-quantising with `reduce_range` still costs 3–7 macro-F1
points ([report](evals/results/2026-10-18-x86-int8-reduce-range/x86_report.md)). Each container
self-tests the model on known cases at start-up and refuses to serve if it gets them wrong.

Limitations: `grounded` is the weakest check (0.69 macro-F1; RAGTruth contexts are often longer than
the 512-token input). The toxicity test set is class-balanced, so production precision will be lower.
English only. A guardrail lowers risk; it does not remove it.

## Layout

```
training/   data prep per check, Laya fine-tune, calibration, ONNX export (fp32 + int8)
evals/      benchmark harness (`make bench`), x86 parity + live checks (evals/x86), dataset licences, committed results
api/        FastAPI service (docs/API.md); deployed to Modal by .github/workflows/deploy-modal.yml (api/modal_app.py)
web/        Next.js site: landing, playground, docs, benchmarks, dashboard (see web/README.md)
sdk/python/ Python client `verdict-guardrails` (sync + async, retries, CI gate); PyPI release pending
docs/       API reference, use cases and design notes
supabase/   database schema for API keys and usage
```

## License

MIT for the code in this repository; the fine-tuned model is Apache-2.0. Datasets and the base model keep their own licences; see
[`evals/DATASETS.md`](evals/DATASETS.md).

## Benchmark

<!-- results:start -->

Held-out test sets, macro-F1 / AUROC ([full report](evals/results/2026-10-17/report.md), generated from [`results.json`](evals/results/2026-10-17/results.json)):

| system | `pii` | `toxicity` | `prompt_injection` | `grounded` |
|---|---|---|---|---|
| Verdict (Laya fine-tuned, fp32) | 0.988 / 0.999 | 0.898 / 0.966 | 0.972 / 0.997 | 0.687 / 0.750 |
| Verdict (Laya fine-tuned, ONNX int8) | 0.988 / 0.999 | 0.899 / 0.966 | 0.973 / 0.997 | 0.693 / 0.749 |
| Laya zero-shot (base) | 0.521 / 0.630 | 0.747 / 0.964 | 0.824 / 0.939 | 0.611 / 0.641 |
| Laya zero-shot (typed-decisions) | 0.517 / 0.650 | 0.698 / 0.960 | 0.757 / 0.950 | 0.563 / 0.642 |
| Presidio (spaCy lg) | 0.820 / 0.898 | – | – | – |
| keyword/regex | – | 0.717 / 0.730 | 0.468 / 0.615 | – |
| NLI zero-shot (deberta-v3-base-zeroshot-v2.0) | 0.516 / 0.579 | 0.756 / 0.860 | 0.435 / 0.608 | 0.503 / 0.484 |
| ProtectAI deberta-v3 injection v2 | – | – | 0.916 / 0.977 | – |
| Qwen3-1.7B judge | 0.604 / 0.698* | 0.559 / 0.774* | 0.550 / 0.763* | 0.408 / 0.456* |

\* LLM judge on a fixed stratified subsample of 200 items per check.

<!-- results:end -->
