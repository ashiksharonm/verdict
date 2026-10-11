# Verdict

Millisecond guardrails and evals for LLM apps. Verdict fine-tunes [Laya](https://huggingface.co/convaiinnovations/laya)
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
api/        FastAPI service (planned)
web/        Next.js site (planned)
sdk/python/ Python client (planned)
docs/       use cases and design notes
```

## License

MIT for the code in this repository. Datasets and base models keep their own licences; see
[`evals/DATASETS.md`](evals/DATASETS.md).
