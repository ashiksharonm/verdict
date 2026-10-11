"""PII: does the text contain personal data?

Positives come from `gretelai/gretel-pii-masking-en-v1` documents (Apache-2.0), which list their
entities by type. None of its documents is PII-free, so negatives are built two ways:

1. **Redacted documents** (in-distribution hard negatives): a different half of the same Gretel
   documents with every PII-type entity replaced by a placeholder (`[EMAIL]`) or a generic phrase
   ("an email address"). Non-identifying entities (dates, cities, companies, URLs) are left in,
   so the model cannot shortcut on "has a date" or "names a company". A redacted document is
   dropped if any PII entity string still occurs in it.
2. **Encyclopedic / open-ended text** from `databricks/databricks-dolly-15k` (CC BY-SA 3.0)
   responses with no source context, filtered to remove anything with an email address or a run
   of 7+ digits. Public figures named in this text are treated as non-PII (PII here means data
   about a private individual); this definitional choice is documented in `evals/DATASETS.md`.

Each Gretel document is used either as a positive or as a redacted negative, never both, and its
uid is its split group.
"""
from __future__ import annotations

import ast
import random
import re
from typing import Any

from .common import group_split, make_record

CHECK = "pii"

PII_TYPES = {
    "name": "NAME", "first_name": "NAME", "last_name": "NAME", "user_name": "USERNAME",
    "email": "EMAIL", "phone_number": "PHONE", "fax_number": "PHONE",
    "street_address": "ADDRESS", "address": "ADDRESS", "postcode": "POSTCODE",
    "date_of_birth": "DOB", "ssn": "ID", "national_id": "ID", "tax_id": "ID",
    "medical_record_number": "ID", "health_plan_beneficiary_number": "ID",
    "customer_id": "ID", "employee_id": "ID", "unique_identifier": "ID", "unique_id": "ID",
    "certificate_license_number": "ID", "license_plate": "ID", "vehicle_identifier": "ID",
    "device_identifier": "ID", "biometric_identifier": "ID",
    "account_number": "ACCOUNT", "bank_routing_number": "ACCOUNT", "swift_bic": "ACCOUNT",
    "credit_card_number": "CARD", "credit_debit_card": "CARD", "cvv": "CARD", "pin": "SECRET",
    "password": "SECRET", "api_key": "SECRET", "ipv4": "IP", "ipv6": "IP", "mac_address": "IP",
    "coordinate": "LOCATION",
}
GENERIC = {
    "NAME": "the person", "USERNAME": "their username", "EMAIL": "an email address",
    "PHONE": "a phone number", "ADDRESS": "their address", "POSTCODE": "a postcode",
    "DOB": "their date of birth", "ID": "an identifier", "ACCOUNT": "an account number",
    "CARD": "a card number", "SECRET": "a credential", "IP": "a network address",
    "LOCATION": "a location",
}
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
_DIGITS = re.compile(r"\d[\d\s().-]{6,}\d")


def pii_entities(entities: list[dict[str, Any]]) -> list[tuple[str, str]]:
    """(surface string, placeholder tag) for every entity with a PII type."""
    out = []
    for e in entities:
        tags = [PII_TYPES[t] for t in e.get("types", []) if t in PII_TYPES]
        if tags and str(e.get("entity", "")).strip():
            out.append((str(e["entity"]).strip(), tags[0]))
    return out


def redact(text: str, ents: list[tuple[str, str]], rng: random.Random) -> str | None:
    """Replace every PII entity; None if any entity string survives."""
    style = rng.random() < 0.5
    # longest first so "Urvashi Jaggi" is replaced before "Jaggi"
    targets = sorted(ents, key=lambda e: -len(e[0]))
    extra = []
    for surface, tag in ents:
        if tag == "NAME":
            extra += [(part, tag) for part in surface.split() if len(part) >= 3]
    for surface, tag in targets + sorted(extra, key=lambda e: -len(e[0])):
        repl = f"[{tag}]" if style else GENERIC[tag]
        text = re.sub(re.escape(surface), repl, text, flags=re.IGNORECASE)
    low = text.casefold()
    if any(s.casefold() in low for s, _ in ents):
        return None
    return text


def gretel_records(rows, seed: int) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    out = []
    for row in rows:
        ents = pii_entities(ast.literal_eval(row["entities"]))
        text = row["text"]
        if not 40 <= len(text) <= 3000:
            continue
        group = f"gretel:{row['uid']}"
        if not ents:
            out.append(make_record(CHECK, {"text": text}, 0, "gretel-no-pii", group))
        elif rng.random() < 0.5:
            out.append(make_record(CHECK, {"text": text}, 1, "gretel", group))
        else:
            red = redact(text, ents, rng)
            if red is not None:
                out.append(make_record(CHECK, {"text": red}, 0, "gretel-redacted", group))
    return out


def dolly_records(rows) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        if row["context"].strip():
            continue
        text = row["response"].strip()
        if not 40 <= len(text) <= 2000 or _EMAIL.search(text) or _DIGITS.search(text):
            continue
        out.append(make_record(CHECK, {"text": text}, 0, "dolly"))
    return out


def build(seed: int) -> dict[str, list[dict[str, Any]]]:
    from datasets import load_dataset

    gretel = load_dataset("gretelai/gretel-pii-masking-en-v1")
    dolly = load_dataset("databricks/databricks-dolly-15k", split="train")
    d = group_split(dolly_records(dolly), {"train": 0.8, "val": 0.05, "test": 0.15}, seed)
    return {
        "train": gretel_records(gretel["train"], seed) + d["train"],
        "val": gretel_records(gretel["validation"], seed + 1) + d["val"],
        "test": gretel_records(gretel["test"], seed + 2) + d["test"],
    }
