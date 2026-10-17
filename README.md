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

Status: work in progress. Training and benchmark code land first; the API, web app and SDK follow.

## Layout

```
training/   data prep per check, Laya fine-tune, calibration, ONNX int8 export
evals/      benchmark harness (`make bench`), dataset licences, committed results
api/        FastAPI service (docs/API.md; Docker Space deploy via scripts/deploy_space.py)
web/        Next.js site: landing, playground, docs, benchmarks, dashboard (see web/README.md)
sdk/python/ Python client `verdict-sdk` (sync + async, retries, CI gate; not on PyPI)
docs/       use cases and design notes
```

## License

MIT for the code in this repository. Datasets and base models keep their own licences; see
[`evals/DATASETS.md`](evals/DATASETS.md).

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
