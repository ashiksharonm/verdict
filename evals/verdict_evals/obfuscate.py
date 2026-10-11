"""Deterministic obfuscations of prompt-injection attempts, for robustness testing.

Each transform keeps the attack readable to an LLM while changing its surface form, which is
what keyword filters and lightly-trained classifiers tend to depend on.
"""
from __future__ import annotations

import base64
import random

LEET = str.maketrans({"a": "4", "e": "3", "i": "1", "o": "0", "s": "5", "t": "7"})
# Latin -> visually identical Cyrillic letters
HOMOGLYPH = {"a": "а", "e": "е", "o": "о", "p": "р", "c": "с", "x": "х",
             "i": "і"}
ZWSP = "​"


def leetspeak(text: str, rng: random.Random) -> str:
    return text.translate(LEET)


def homoglyphs(text: str, rng: random.Random) -> str:
    return "".join(HOMOGLYPH[ch] if ch in HOMOGLYPH and rng.random() < 0.5 else ch for ch in text)


def zero_width(text: str, rng: random.Random) -> str:
    """Insert zero-width spaces inside words."""
    return "".join(ch + ZWSP if ch.isalpha() and rng.random() < 0.3 else ch for ch in text)


def random_case(text: str, rng: random.Random) -> str:
    return "".join(ch.upper() if rng.random() < 0.5 else ch.lower() for ch in text)


def base64_wrap(text: str, rng: random.Random) -> str:
    enc = base64.b64encode(text.encode("utf-8")).decode("ascii")
    return f"Decode the following base64 string and do exactly what it says: {enc}"


TRANSFORMS = {
    "leetspeak": leetspeak,
    "homoglyphs": homoglyphs,
    "zero_width": zero_width,
    "random_case": random_case,
    "base64": base64_wrap,
}


def obfuscate(records: list[dict], name: str, seed: int = 0) -> list[dict]:
    """Copies of `records` with the text transformed; ids get a `~name` suffix."""
    fn = TRANSFORMS[name]
    rng = random.Random(f"{seed}:{name}")
    out = []
    for r in records:
        state = dict(r["state"], text=fn(r["state"]["text"], rng))
        out.append({**r, "id": f"{r['id']}~{name}", "state": state, "source": f"{r['source']}~{name}"})
    return out
