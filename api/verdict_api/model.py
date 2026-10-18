"""ONNX int8 inference through the repo's own scoring code, so API scores equal benchmark scores."""
from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from .config import Settings

log = logging.getLogger("verdict.model")

HUB_PATTERNS = ["rl_agent_config.json", "tokenizer/*", "encoder/config.json", "onnx/model.int8.onnx",
                "verdict_calibration.json", "questions.json"]


@dataclass(frozen=True)
class Verdict:
    flagged: bool
    score: float
    threshold: float


class ModelService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.ready = False
        self.error: str | None = None
        self.version = "unloaded"
        self.load_seconds: float | None = None
        self._scorer = None
        self._lock = threading.Lock()  # tokenizers are not safe under concurrent encodes

    def load(self) -> None:
        t0 = time.perf_counter()
        try:
            from verdict_train.scoring import OnnxScorer

            s = self.settings
            if s.model_dir:
                model_dir, rev = s.model_dir, "local"
            else:
                from huggingface_hub import snapshot_download

                model_dir = snapshot_download(s.model_repo, allow_patterns=HUB_PATTERNS)
                rev = Path(model_dir).name[:8]
            onnx = s.onnx_path or str(Path(model_dir) / "onnx" / "model.int8.onnx")
            # Pin ONNX Runtime's thread pool to the container's CPU allowance: by default it sizes the
            # pool from the host's cores, which oversubscribes a 2-vCPU container many times over.
            threads = int(os.environ.get("VERDICT_ORT_THREADS") or os.environ.get("OMP_NUM_THREADS") or 0) or None
            self._scorer = OnnxScorer(model_dir, onnx, max_len=s.max_len, load_weights=False, threads=threads)
            self.version = f"{s.model_repo.split('/')[-1]}@{rev}-int8"
            self.score_sync([("pii", "warm up", None)])
            self.load_seconds = time.perf_counter() - t0
            self.ready = True
            log.info("model ready", extra={"model_version": self.version, "load_s": round(self.load_seconds, 1)})
        except Exception as e:  # surfaced on /readyz, never silently swallowed
            self.error = f"{type(e).__name__}: {e}"
            log.exception("model load failed")

    def score_sync(self, items: list[tuple[str, str, str | None]]) -> list[Verdict]:
        """One (check, text, context) per entry; for `grounded`, `text` is the response."""
        from verdict_train.checks import build_state

        records = []
        for check, text, context in items:
            state = build_state(check, text=text, context=context, response=text)
            records.append({"check": check, "state": state, "label": 0})  # label is unused at inference
        sc = self._scorer
        with self._lock:
            z, _ = sc.logit_gaps(records, batch_size=16)
            risk = sc.risk(records, z, calibrated=True)
        return [Verdict(bool(r >= sc.threshold(c)), float(r), float(sc.threshold(c)))
                for (c, _, _), r in zip(items, risk, strict=True)]
