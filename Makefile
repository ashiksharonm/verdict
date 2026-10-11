PY ?= .venv/bin/python
DATE ?= $(shell date +%Y-%m-%d)

.PHONY: data train calibrate export bench smoke test lint

data:          ## build processed train/val/test splits
	$(PY) -m verdict_train.prepare

train:         ## fine-tune the multi-check Laya model (Apple MPS / CUDA / CPU)
	$(PY) -m verdict_train.finetune --config training/configs/train.yaml

calibrate:     ## per-check temperature + threshold on val
	$(PY) -m verdict_train.calibrate --model artifacts/verdict-laya

export:        ## ONNX fp32 + int8, parity and CPU latency
	$(PY) -m verdict_train.export_onnx --model artifacts/verdict-laya

bench:         ## full benchmark on the held-out test sets
	$(PY) -m verdict_evals.run --out evals/results/$(DATE)
	$(PY) -m verdict_evals.report evals/results/$(DATE) --readme README.md

smoke:         ## harness smoke run on the fixture
	$(PY) -m verdict_evals.run --fixture --systems tfidf keyword --latency-only --n-boot 100 --out /tmp/verdict-smoke

test:
	$(PY) -m pytest -q

lint:
	$(PY) -m ruff check .
