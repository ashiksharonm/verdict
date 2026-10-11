"""Per-check dataset builders. Each module exposes `CHECK` and `build(seed) -> {split: records}`."""
from . import grounded, pii, prompt_injection, toxicity

BUILDERS = {m.CHECK: m for m in (pii, toxicity, prompt_injection, grounded)}
