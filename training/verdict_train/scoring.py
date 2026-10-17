"""Batch scoring of Verdict records with a Laya checkpoint, in PyTorch or ONNX Runtime.

Both backends share one preprocessing path, the one `laya.train` trains on
(`items_from_rows` -> `encode_item` -> `collate_items`), so a probability difference between them
is the backend's, never the tokenisation's. Scores are the raw yes-vs-no logit gap `z`;
`p_yes = sigmoid(z / T)` for a temperature `T`.
"""
from __future__ import annotations

import json
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np

from .checks import CHECKS, laya_row, risk_from_yes

NOUL_QTYPE_INDEX = 2  # laya.common.QTYPES order: choice, score, noul


def sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


def _load_tokenizer_and_config(model_dir: str):
    """The tokenizer and `rl_agent_config.json` exactly as `laya.train.load_checkpoint` reads them."""
    from laya.agent import _fix_tokenizer_config
    from transformers import AutoTokenizer

    _fix_tokenizer_config(model_dir)
    cfg = json.loads((Path(model_dir) / "rl_agent_config.json").read_text(encoding="utf-8"))
    return AutoTokenizer.from_pretrained(str(Path(model_dir) / "tokenizer")), cfg


class _Base:
    def __init__(self, model_dir: str, max_len: int | None = None, load_weights: bool = True):
        from laya.train import load_checkpoint, resolve_checkpoint_dir

        self.model_dir = resolve_checkpoint_dir(model_dir)
        if load_weights:
            self._model, self.tok, self.cfg = load_checkpoint(self.model_dir)
        else:  # tokenizer + config only: what the ONNX path needs, without the 840 MB safetensors
            self._model = None
            self.tok, self.cfg = _load_tokenizer_and_config(self.model_dir)
        self.max_len = int(max_len or self.cfg.get("max_len", 512))
        self.head_max_len = int(self.cfg.get("head_max_len", 192))
        temps = self.cfg.get("temperature") or [1.0, 1.0, 1.0]
        self.default_temperature = float(temps[NOUL_QTYPE_INDEX])
        calib = Path(self.model_dir) / "verdict_calibration.json"
        self.calibration = json.loads(calib.read_text()) if calib.exists() else None

    def items(self, records: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
        from laya.train import items_from_rows

        items, skipped = items_from_rows(self.tok, [laya_row(r) for r in records], self.max_len,
                                         self.head_max_len)
        if skipped or len(items) != len(records):
            raise ValueError(f"{len(records) - len(items)} records could not be encoded: {skipped}")
        return items

    def batch(self, items: Sequence[dict[str, Any]]) -> dict[str, Any]:
        from laya.common import collate_items
        from laya.train import encode_item

        enc = [encode_item(self.tok, it, self.max_len, self.head_max_len) for it in items]
        return collate_items([enc], self.tok.pad_token_id)

    def _logits(self, batch) -> np.ndarray:  # (n, k) raw option logits
        raise NotImplementedError

    def logit_gaps(self, records: Sequence[dict[str, Any]], batch_size: int = 16,
                   sort_by_length: bool = True) -> tuple[np.ndarray, list[float]]:
        """`z = logit(yes) - logit(no)` per record, and the wall time of every batch."""
        items = self.items(records)
        order = list(range(len(items)))
        if sort_by_length:  # less padding; results are put back in input order
            order.sort(key=lambda i: len(items[i]["state_ids"]))
        z = np.zeros(len(items), dtype=np.float64)
        times = []
        for start in range(0, len(order), batch_size):
            idx = order[start:start + batch_size]
            t0 = time.perf_counter()
            logits = self._logits(self.batch([items[i] for i in idx]))
            times.append(time.perf_counter() - t0)
            z[idx] = logits[:, 1] - logits[:, 0]  # noul options are [false, true]
        return z, times

    def risk(self, records: Sequence[dict[str, Any]], z: np.ndarray,
             calibrated: bool = True) -> np.ndarray:
        """Probability that each record's check fires, after temperature scaling."""
        out = np.zeros(len(records))
        for i, r in enumerate(records):
            t = self.temperature(r["check"]) if calibrated else self.default_temperature
            out[i] = risk_from_yes(r["check"], float(sigmoid(np.asarray(z[i] / t))))
        return out

    def temperature(self, check: str) -> float:
        if self.calibration:
            return float(self.calibration["checks"][check]["temperature"])
        return self.default_temperature

    def threshold(self, check: str) -> float:
        if self.calibration:
            return float(self.calibration["checks"][check]["threshold"])
        return 0.5


class TorchScorer(_Base):
    def __init__(self, model_dir: str, device: str = "cpu", max_len: int | None = None):
        import torch

        super().__init__(model_dir, max_len)
        self.torch = torch
        self.device = torch.device(device)
        self.model = self._model.to(self.device).eval()

    def _logits(self, batch) -> np.ndarray:
        torch = self.torch
        with torch.inference_mode():
            logits, _ = self.model(batch["input_ids"].to(self.device), batch["attention_mask"].to(self.device),
                                   batch["marker_pos"].to(self.device), batch["marker_mask"].to(self.device),
                                   batch["qtype"].to(self.device))
            if self.device.type == "mps":
                torch.mps.synchronize()
            return logits.float().cpu().numpy()


class OnnxScorer(_Base):
    def __init__(self, model_dir: str, onnx_path: str, max_len: int | None = None, threads: int | None = None,
                 load_weights: bool = True):
        import onnxruntime as ort

        super().__init__(model_dir, max_len, load_weights=load_weights)
        del self._model
        so = ort.SessionOptions()
        so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        if threads:
            so.intra_op_num_threads = threads
        self.session = ort.InferenceSession(onnx_path, sess_options=so, providers=["CPUExecutionProvider"])

    def _logits(self, batch) -> np.ndarray:
        feeds = {
            "input_ids": batch["input_ids"].numpy().astype(np.int64),
            "attention_mask": batch["attention_mask"].numpy().astype(np.int64),
            "marker_pos": batch["marker_pos"].numpy().astype(np.int64),
            "marker_mask": batch["marker_mask"].numpy().astype(bool),
            "qtype": batch["qtype"].numpy().astype(np.int64),
        }
        return self.session.run(["logits"], feeds)[0]


def fit_temperature(z: np.ndarray, y_yes: np.ndarray) -> float:
    """Temperature minimising the binary NLL of `sigmoid(z / T)` against yes-labels (grid + refine)."""
    z = np.asarray(z, dtype=np.float64)
    y = np.asarray(y_yes, dtype=np.float64)

    def nll(t: float) -> float:
        p = np.clip(sigmoid(z / t), 1e-7, 1 - 1e-7)
        return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))

    grid = np.exp(np.linspace(np.log(0.05), np.log(20.0), 200))
    best = min(grid, key=nll)
    lo, hi = best / 1.05, best * 1.05
    for _ in range(60):  # golden-section refine
        a = hi - (hi - lo) / 1.618
        b = lo + (hi - lo) / 1.618
        lo, hi = (lo, b) if nll(a) < nll(b) else (a, hi)
    return float((lo + hi) / 2)


def yes_labels(records: Sequence[dict[str, Any]]) -> np.ndarray:
    """1 where the correct Laya answer is yes (label flipped for checks whose yes means pass)."""
    return np.array([int(r["label"]) if CHECKS[r["check"]].yes_fires else 1 - int(r["label"])
                     for r in records])
