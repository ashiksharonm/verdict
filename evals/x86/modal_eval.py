"""Score the held-out test sets with an int8 ONNX export on Modal's x86 CPUs.

    modal run evals/x86/modal_eval.py --onnx artifacts/onnx/model.int8.onnx --out evals/results/<dir>

Modal schedules containers on mixed hardware (AMD without VNNI, AMD/Intel with VNNI), which is
what the production API sees, so each shard records the CPU it ran on. Scores go to
`x86_predictions.jsonl`; `evals/x86/compare.py` turns them into metrics next to the benchmark.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import modal

_here = Path(__file__).resolve()
if len(_here.parents) > 2 and (_here.parents[2] / "api").is_dir():  # local run; in the container the module is mounted
    sys.path.insert(0, str(_here.parents[2] / "api"))
from modal_app import image  # noqa: E402  (the production image)

CHECKS = ["pii", "toxicity", "prompt_injection", "grounded"]
app = modal.App("verdict-x86-eval")


def build_image(onnx_path: str) -> modal.Image:
    img = image.add_local_file(onnx_path, "/opt/eval/model.onnx")
    for c in CHECKS:
        img = img.add_local_file(f"data/processed/{c}/test.jsonl", f"/opt/eval/data/{c}/test.jsonl")
    return img


ONNX = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--onnx=")), None) or \
    (sys.argv[sys.argv.index("--onnx") + 1] if "--onnx" in sys.argv else "artifacts/onnx/model.int8.onnx")


@app.function(image=build_image(ONNX), cpu=1.0, memory=4096, timeout=3600, max_containers=8)
def score_shard(ids: list[str]) -> dict:
    import time

    from huggingface_hub import snapshot_download
    from verdict_api.model import HUB_PATTERNS
    from verdict_train.scoring import OnnxScorer

    flags_line = next(line for line in open("/proc/cpuinfo") if line.startswith("flags")).split()
    vendor = next((line.split(":", 1)[1].strip() for line in open("/proc/cpuinfo") if line.startswith("vendor_id")), "?")
    want = set(ids)
    records = [r for c in CHECKS for r in map(json.loads, open(f"/opt/eval/data/{c}/test.jsonl")) if r["id"] in want]
    d = snapshot_download("ashiksharon005/verdict-laya", allow_patterns=HUB_PATTERNS)
    sc = OnnxScorer(d, "/opt/eval/model.onnx", max_len=512, load_weights=False, threads=2)
    t = time.time()
    z, _ = sc.logit_gaps(records, batch_size=16)
    risk = sc.risk(records, z, calibrated=True)
    return {"cpu": {"vendor": vendor, "vnni": "avx512_vnni" in flags_line or "avx_vnni" in flags_line},
            "seconds": time.time() - t, "rows": [{"id": r["id"], "check": r["check"], "score": float(p)} for r, p in zip(records, risk, strict=True)]}


@app.local_entrypoint()
def main(onnx: str = "artifacts/onnx/model.int8.onnx", out: str = "evals/results/x86", shards: int = 8):
    ids = [json.loads(line)["id"] for c in CHECKS for line in open(f"data/processed/{c}/test.jsonl")]
    parts = [ids[i::shards] for i in range(shards)]
    Path(out).mkdir(parents=True, exist_ok=True)
    meta = []
    with open(Path(out) / "x86_predictions.jsonl", "w") as f:
        for res in score_shard.map(parts):
            meta.append({"cpu": res["cpu"], "items": len(res["rows"]), "seconds": round(res["seconds"], 1)})
            for row in res["rows"]:
                f.write(json.dumps(row | {"cpu_vendor": res["cpu"]["vendor"], "vnni": res["cpu"]["vnni"]}) + "\n")
    (Path(out) / "x86_shards.json").write_text(json.dumps({"onnx": onnx, "shards": meta}, indent=2))
    print(json.dumps(meta))
