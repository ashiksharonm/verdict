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
# Pinned Hub commit (fp32 ONNX added). Bump deliberately; the image rebuilds when this changes.
MODEL_REVISION = "5a21230f3fed391f25a78af65d538ae459a8d632"
# fp32 on x86: the int8 graph saturates or loses accuracy on Modal's CPUs (evals/results/2026-10-18-x86-*).
ONNX_FILE = "onnx/model.onnx"
HF_HOME = "/opt/hf"
# Same files the API's own loader asks for (api/verdict_api/model.py HUB_PATTERNS).
HUB_PATTERNS = ["rl_agent_config.json", "tokenizer/*", "encoder/config.json", ONNX_FILE,
                "verdict_calibration.json", "questions.json"]


def download_model() -> None:
    from huggingface_hub import snapshot_download

    snapshot_download(MODEL_REPO, revision=MODEL_REVISION, allow_patterns=HUB_PATTERNS)


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
        "OMP_NUM_THREADS": "4",
        "VERDICT_ORT_THREADS": "4",  # 2 physical cores = 4 vCPU; Modal overrides OMP_NUM_THREADS
        "VERDICT_ONNX_FILE": ONNX_FILE,
        "VERDICT_MODEL_REVISION": MODEL_REVISION,
    })
    .add_local_dir("api/verdict_api", "/app/api/verdict_api", ignore=["__pycache__"])
    .add_local_file("training/verdict_train/__init__.py", "/app/training/verdict_train/__init__.py")
    .add_local_file("training/verdict_train/checks.py", "/app/training/verdict_train/checks.py")
    .add_local_file("training/verdict_train/scoring.py", "/app/training/verdict_train/scoring.py")
)

app = modal.App("verdict-api")


@app.cls(
    image=image,
    secrets=[modal.Secret.from_name("verdict-api")],
    cpu=2.0,  # two physical cores (4 vCPU): fp32 needs the headroom
    memory=4096,  # fp32 graph is 1.7 GB
    min_containers=0,  # scale to zero when idle; the first request after that is a cold start
    max_containers=2,  # hard cap on spend
    scaledown_window=120,  # short idle window: the free tier is $1/month without a card
    timeout=60,
)
@modal.concurrent(max_inputs=16)
class Api:
    @modal.enter()
    def load(self) -> None:
        """Load and self-test the model before Modal routes any request to this container.

        A self-test failure raises, so the container never serves and Modal starts another one.
        """
        from verdict_api.app import create_app
        from verdict_api.config import Settings
        from verdict_api.model import ModelService

        settings = Settings.from_env()
        self.model = ModelService(settings)
        self.model.load(strict=True)
        self.web_app = create_app(settings, model=self.model)

    @modal.asgi_app(label="verdict-api")
    def web(self):
        return self.web_app
