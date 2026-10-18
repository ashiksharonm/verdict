"""Serve the Verdict API on Modal (CPU, scales to zero).

    modal deploy api/modal_app.py        # from the repo root

The int8 ONNX model is downloaded from the Hub while the image builds, so a cold start loads it
from local disk instead of fetching 443 MB. Runtime config comes from the Modal secret
`verdict-api` (same variable names as `api/verdict_api/config.py`); the deploy workflow creates it
from the repository's GitHub secrets.
"""
from __future__ import annotations

import modal

MODEL_REPO = "ashiksharon005/verdict-laya"
HF_HOME = "/opt/hf"
# Same files the API's own loader asks for (api/verdict_api/model.py HUB_PATTERNS).
HUB_PATTERNS = ["rl_agent_config.json", "tokenizer/*", "encoder/config.json", "onnx/model.int8.onnx",
                "verdict_calibration.json", "questions.json"]


def download_model() -> None:
    from huggingface_hub import snapshot_download

    snapshot_download(MODEL_REPO, allow_patterns=HUB_PATTERNS)


image = (
    modal.Image.debian_slim(python_version="3.11")
    # CPU-only torch: laya imports it for tensor collation; inference runs on onnxruntime.
    .pip_install("torch==2.14.1", index_url="https://download.pytorch.org/whl/cpu")
    .pip_install_from_requirements("api/requirements.txt")
    .env({"HF_HOME": HF_HOME})
    .run_function(download_model)
    .env({
        "HF_HUB_OFFLINE": "1",  # serve the baked-in snapshot; never fetch at request time
        "PYTHONPATH": "/app/api:/app/training",
        "TOKENIZERS_PARALLELISM": "false",
        "OMP_NUM_THREADS": "2",
    })
    .add_local_dir("api/verdict_api", "/app/api/verdict_api", ignore=["__pycache__"])
    .add_local_file("training/verdict_train/__init__.py", "/app/training/verdict_train/__init__.py")
    .add_local_file("training/verdict_train/checks.py", "/app/training/verdict_train/checks.py")
    .add_local_file("training/verdict_train/scoring.py", "/app/training/verdict_train/scoring.py")
)

app = modal.App("verdict-api")


@app.function(
    image=image,
    secrets=[modal.Secret.from_name("verdict-api")],
    cpu=1.0,  # one physical core (2 vCPU)
    memory=2048,
    min_containers=0,  # scale to zero when idle; the first request after that is a cold start
    max_containers=2,  # hard cap on spend
    scaledown_window=300,
    timeout=60,
)
@modal.concurrent(max_inputs=16)
@modal.asgi_app(label="verdict-api")
def api():
    from verdict_api.app import app_factory

    return app_factory()
