"""Per-check dataset builders. Each module exposes `CHECK` and `build(seed) -> {split: records}`.

Builders are imported on demand: some need the optional `data` extra (pandas, datasets),
which the tests and CI do not install.
"""
from importlib import import_module

MODULES = {"pii": "pii", "toxicity": "toxicity", "prompt_injection": "prompt_injection", "grounded": "grounded"}


def builder(check: str):
    """The builder module for `check`, imported on first use."""
    return import_module(f"{__name__}.{MODULES[check]}")
