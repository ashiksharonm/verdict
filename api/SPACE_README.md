---
title: Verdict API
emoji: 🛡️
colorFrom: indigo
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
license: mit
short_description: Guardrail checks API (PII, toxicity, prompt injection, groundedness)
---

# Verdict API

FastAPI service for [Verdict](https://github.com/ashiksharonm/verdict): calibrated `pii`, `toxicity`,
`prompt_injection` and `grounded` checks from one int8 ONNX model on CPU. Contract: `docs/API.md` in the repository,
OpenAPI at `/docs`.
