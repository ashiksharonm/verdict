# Verdict benchmark — 2026-10-17

Hardware: Apple M5, 16 GB unified memory (macOS-27.0.1-arm64-arm-64bit); torch 2.14.1, transformers 5.19.0, onnxruntime 1.31.0, laya 0.4.2.
Bootstrap: 1000 resamples, 95% percentile intervals. Scores are the probability that the check fires; Verdict uses per-check thresholds fitted on val, every other system its natural rule (0.5, or a hard 0/1 output).

## Summary (macro-F1 / AUROC)

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

\* LLM judge scored on a fixed stratified subsample of 200 items per check.

## Per-check metrics

### `pii` (test n = 2000)

| system | thr | macro-F1 [95% CI] | precision | recall | AUROC [95% CI] | ECE | Brier | recall@1%FPR | recall@5%FPR |
|---|---|---|---|---|---|---|---|---|---|
| Verdict (Laya fine-tuned, fp32) | 0.63 | 0.988 [0.983, 0.992] | 0.989 | 0.987 | 0.999 [0.999, 1.000] | 0.006 | 0.009 | 0.987 | 0.997 |
| Verdict (Laya fine-tuned, ONNX int8) | 0.63 | 0.988 [0.983, 0.992] | 0.990 | 0.986 | 0.999 [0.998, 1.000] | 0.006 | 0.009 | 0.988 | 0.997 |
| Laya zero-shot (base) | 0.50 | 0.521 [0.498, 0.543] | 0.636 | 0.276 | 0.630 [0.605, 0.655] | 0.276 | 0.325 | 0.036 | 0.114 |
| Laya zero-shot (typed-decisions) | 0.50 | 0.517 [0.495, 0.540] | 0.657 | 0.257 | 0.650 [0.626, 0.674] | 0.247 | 0.315 | 0.046 | 0.126 |
| Presidio (spaCy lg) | 0.50 | 0.820 [0.802, 0.837] | 0.819 | 0.821 | 0.898 [0.885, 0.912] | 0.114 | 0.136 | 0.353 | 0.353 |
| NLI zero-shot (deberta-v3-base-zeroshot-v2.0) | 0.50 | 0.516 [0.494, 0.539] | 0.613 | 0.279 | 0.579 [0.554, 0.606] | 0.383 | 0.400 | 0.034 | 0.087 |
| Qwen3-1.7B judge (n=200 subsample) | 0.50 | 0.604 [0.533, 0.675] | 0.700 | 0.420 | 0.698 [0.629, 0.776] | 0.367 | 0.363 | 0.040 | 0.180 |

### `toxicity` (test n = 2000)

| system | thr | macro-F1 [95% CI] | precision | recall | AUROC [95% CI] | ECE | Brier | recall@1%FPR | recall@5%FPR |
|---|---|---|---|---|---|---|---|---|---|
| Verdict (Laya fine-tuned, fp32) | 0.53 | 0.898 [0.885, 0.911] | 0.911 | 0.883 | 0.966 [0.959, 0.972] | 0.022 | 0.072 | 0.571 | 0.781 |
| Verdict (Laya fine-tuned, ONNX int8) | 0.53 | 0.899 [0.885, 0.911] | 0.912 | 0.883 | 0.966 [0.959, 0.972] | 0.023 | 0.073 | 0.563 | 0.773 |
| Laya zero-shot (base) | 0.50 | 0.747 [0.727, 0.766] | 0.981 | 0.530 | 0.964 [0.956, 0.970] | 0.073 | 0.157 | 0.531 | 0.778 |
| Laya zero-shot (typed-decisions) | 0.50 | 0.698 [0.678, 0.718] | 0.985 | 0.448 | 0.960 [0.952, 0.967] | 0.061 | 0.163 | 0.531 | 0.777 |
| keyword/regex (0/1 output) | 0.50 | 0.717 [0.696, 0.738] | 0.908 | 0.512 | 0.730 [0.713, 0.748] | 0.270 | 0.270 | 0.000 | 0.000 |
| NLI zero-shot (deberta-v3-base-zeroshot-v2.0) | 0.50 | 0.756 [0.738, 0.775] | 0.837 | 0.645 | 0.860 [0.843, 0.875] | 0.201 | 0.215 | 0.208 | 0.400 |
| Qwen3-1.7B judge (n=200 subsample) | 0.50 | 0.559 [0.483, 0.627] | 0.844 | 0.270 | 0.774 [0.708, 0.838] | 0.382 | 0.378 | 0.090 | 0.290 |

### `prompt_injection` (test n = 1249)

| system | thr | macro-F1 [95% CI] | precision | recall | AUROC [95% CI] | ECE | Brier | recall@1%FPR | recall@5%FPR |
|---|---|---|---|---|---|---|---|---|---|
| Verdict (Laya fine-tuned, fp32) | 0.74 | 0.972 [0.962, 0.982] | 0.993 | 0.974 | 0.997 [0.995, 0.998] | 0.013 | 0.017 | 0.966 | 0.988 |
| Verdict (Laya fine-tuned, ONNX int8) | 0.74 | 0.973 [0.963, 0.982] | 0.993 | 0.975 | 0.997 [0.995, 0.998] | 0.011 | 0.017 | 0.966 | 0.987 |
| Laya zero-shot (base) | 0.50 | 0.824 [0.802, 0.846] | 0.994 | 0.776 | 0.939 [0.926, 0.951] | 0.139 | 0.145 | 0.767 | 0.846 |
| Laya zero-shot (typed-decisions) | 0.50 | 0.757 [0.732, 0.780] | 0.998 | 0.673 | 0.950 [0.938, 0.961] | 0.160 | 0.203 | 0.735 | 0.816 |
| keyword/regex (0/1 output) | 0.50 | 0.468 [0.440, 0.495] | 0.936 | 0.277 | 0.615 [0.597, 0.634] | 0.529 | 0.529 | 0.000 | 0.277 |
| NLI zero-shot (deberta-v3-base-zeroshot-v2.0) | 0.50 | 0.435 [0.406, 0.461] | 0.990 | 0.222 | 0.608 [0.578, 0.639] | 0.516 | 0.524 | 0.266 | 0.357 |
| ProtectAI deberta-v3 injection v2 | 0.50 | 0.916 [0.899, 0.930] | 0.971 | 0.928 | 0.977 [0.967, 0.984] | 0.068 | 0.068 | 0.802 | 0.918 |
| Qwen3-1.7B judge (n=200 subsample) | 0.50 | 0.550 [0.473, 0.615] | 0.965 | 0.385 | 0.763 [0.690, 0.829] | 0.410 | 0.417 | 0.245 | 0.441 |

### `grounded` (test n = 1200)

| system | thr | macro-F1 [95% CI] | precision | recall | AUROC [95% CI] | ECE | Brier | recall@1%FPR | recall@5%FPR |
|---|---|---|---|---|---|---|---|---|---|
| Verdict (Laya fine-tuned, fp32) | 0.40 | 0.687 [0.662, 0.714] | 0.569 | 0.683 | 0.750 [0.721, 0.779] | 0.030 | 0.192 | 0.026 | 0.140 |
| Verdict (Laya fine-tuned, ONNX int8) | 0.40 | 0.693 [0.668, 0.721] | 0.576 | 0.685 | 0.749 [0.719, 0.777] | 0.034 | 0.192 | 0.028 | 0.133 |
| Laya zero-shot (base) | 0.50 | 0.611 [0.584, 0.639] | 0.475 | 0.783 | 0.641 [0.610, 0.673] | 0.139 | 0.257 | 0.005 | 0.023 |
| Laya zero-shot (typed-decisions) | 0.50 | 0.563 [0.537, 0.592] | 0.440 | 0.807 | 0.642 [0.612, 0.674] | 0.182 | 0.284 | 0.002 | 0.030 |
| NLI zero-shot (deberta-v3-base-zeroshot-v2.0) | 0.50 | 0.503 [0.476, 0.533] | 0.371 | 0.275 | 0.484 [0.448, 0.520] | 0.337 | 0.370 | 0.007 | 0.030 |
| Qwen3-1.7B judge (n=200 subsample) | 0.50 | 0.408 [0.367, 0.455] | 0.286 | 0.028 | 0.456 [0.380, 0.538] | 0.374 | 0.371 | 0.000 | 0.028 |

**`prompt_injection` macro-F1 by source**

| system | deepset (n=116) | jackhhao (n=236) | spml (n=897) |
|---|---|---|---|
| Verdict (Laya fine-tuned, fp32) | 0.896 | 0.983 | 0.978 |
| Verdict (Laya fine-tuned, ONNX int8) | 0.896 | 0.983 | 0.980 |
| Laya zero-shot (base) | 0.710 | 0.987 | 0.774 |
| Laya zero-shot (typed-decisions) | 0.653 | 0.996 | 0.687 |
| keyword/regex | 0.396 | 0.732 | 0.395 |
| NLI zero-shot (deberta-v3-base-zeroshot-v2.0) | 0.530 | 0.379 | 0.404 |
| ProtectAI deberta-v3 injection v2 | 0.642 | 0.910 | 0.947 |
| Qwen3-1.7B judge | 0.629 | 0.757 | 0.479 |

**`grounded` macro-F1 by source**

| system | ragtruth-data2txt (n=432) | ragtruth-qa (n=382) | ragtruth-summary (n=386) |
|---|---|---|---|
| Verdict (Laya fine-tuned, fp32) | 0.384 | 0.573 | 0.477 |
| Verdict (Laya fine-tuned, ONNX int8) | 0.384 | 0.579 | 0.489 |
| Laya zero-shot (base) | 0.408 | 0.521 | 0.488 |
| Laya zero-shot (typed-decisions) | 0.405 | 0.515 | 0.424 |
| NLI zero-shot (deberta-v3-base-zeroshot-v2.0) | 0.431 | 0.508 | 0.558 |
| Qwen3-1.7B judge | 0.281 | 0.553 | 0.443 |

## Latency and throughput

| system | device | batch-1 p50 ms | batch-1 p95 ms | throughput (items/s) at batch |
|---|---|---|---|---|
| Verdict (Laya fine-tuned, fp32) | mps | 87.3 | 249.5 | 9.9 @ 16 |
| Verdict (Laya fine-tuned, ONNX int8) | cpu (onnxruntime) | 102.2 | 544.7 | 5.4 @ 16 |
| Laya zero-shot (base) | mps | 98.3 | 314.9 | 7.2 @ 16 |
| Laya zero-shot (typed-decisions) | mps | 67.8 | 208.0 | 9.6 @ 16 |
| Presidio (spaCy lg) | cpu | 6.8 | 16.2 | 120.4 @ 1 |
| keyword/regex | cpu | 0.0 | 0.2 | 24443.6 @ 1 |
| NLI zero-shot (deberta-v3-base-zeroshot-v2.0) | mps | 23.7 | 155.6 | 22.8 @ 16 |
| ProtectAI deberta-v3 injection v2 | mps | 29.4 | 213.4 | 21.5 @ 16 |
| Qwen3-1.7B judge | mps | 139.5 | 764.7 | 4.0 @ 1 |
| Verdict fp32 (PyTorch CPU) | cpu | 123.1 | 396.9 | 6.3 @ 16 |
| Verdict fp32 (ONNX CPU) | cpu (onnxruntime) | 112.5 | 513.5 | 4.9 @ 16 |

## Prompt-injection robustness (recall on obfuscated attacks)

Every positive in the injection test set, rewritten five ways (`evals/verdict_evals/obfuscate.py`).

| system | original recall | leetspeak | homoglyphs | zero_width | random_case | base64 |
|---|---|---|---|---|---|---|
| Verdict (Laya fine-tuned, fp32) | 0.974 | 1.000 | 0.980 | 0.971 | 0.998 | 1.000 |
| Verdict (Laya fine-tuned, ONNX int8) | 0.975 | 0.999 | 0.979 | 0.963 | 0.999 | 1.000 |
| Laya zero-shot (base) | 0.776 | 0.998 | 0.932 | 0.938 | 0.997 | 1.000 |
| Laya zero-shot (typed-decisions) | 0.673 | 0.974 | 0.891 | 0.924 | 0.988 | 1.000 |
| keyword/regex | 0.277 | 0.029 | 0.048 | 0.054 | 0.277 | 0.000 |
| NLI zero-shot (deberta-v3-base-zeroshot-v2.0) | 0.222 | 0.001 | 0.048 | 0.001 | 0.012 | 0.000 |
| ProtectAI deberta-v3 injection v2 | 0.928 | 0.989 | 0.946 | 0.999 | 0.999 | 1.000 |

## Verdict vs LLM judge on the same subsample

| check | n | Verdict macro-F1 | judge macro-F1 | Verdict − judge AUROC [95% CI] | Cohen's κ |
|---|---|---|---|---|---|
| `pii` | 200 | 0.990 | 0.604 | 0.301 [0.223, 0.371] | 0.254 |
| `toxicity` | 200 | 0.910 | 0.559 | 0.199 [0.135, 0.263] | 0.231 |
| `prompt_injection` | 200 | 0.982 | 0.550 | 0.235 [0.170, 0.306] | 0.258 |
| `grounded` | 200 | 0.677 | 0.408 | 0.288 [0.156, 0.409] | -0.049 |

## Cost per 1M checks

- **Self-hosted Verdict (ONNX int8, CPU)**: 5.4 checks/s measured on the M5 CPU over the full test set at batch 16 → 51.5 CPU-machine-hours per 1M checks. On a free Hugging Face CPU Space the marginal cost is $0 (throughput there is not yet measured).
- **Reference only — OpenAI gpt-4o-mini as judge**: 346 prompt tokens/check (mean of the judge prompts above, Qwen tokenizer) × $0.15/M input + 1 output token × $0.6/M ≈ **$52 per 1M checks** (list price from developers.openai.com/api/docs/pricing (standard tier), read 2026-10-11).
- **Reference only — OpenAI gpt-4.1-mini as judge**: 346 prompt tokens/check (mean of the judge prompts above, Qwen tokenizer) × $0.4/M input + 1 output token × $1.6/M ≈ **$140 per 1M checks** (list price from developers.openai.com/api/docs/pricing (standard tier), read 2026-10-11).

