# api

FastAPI service behind `https://ashiksharon005-verdict-api.hf.space` (a free Hugging Face Docker Space).
Contract: [`docs/API.md`](../docs/API.md).

```bash
pip install -e ".[dev,api]" laya==0.4.2 transformers onnxruntime torch
VERDICT_MODEL_DIR=artifacts/verdict-laya VERDICT_ONNX_PATH=artifacts/hub/onnx/model.int8.onnx \
  uvicorn verdict_api.app:app_factory --factory --port 7860 --app-dir api
pytest api/tests          # mocked Supabase/Redis/Turnstile; the real-model test skips if no checkpoint is cached
```

Scoring goes through `training/verdict_train/scoring.py` (`OnnxScorer`), the same path the benchmark uses, with the
calibrated temperature and threshold per check from `verdict_calibration.json`. Inputs are truncated to 512 tokens.
Deploy: `.github/workflows/deploy-api.yml`. Config: [`.env.example`](.env.example).
