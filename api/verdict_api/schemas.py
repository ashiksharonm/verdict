from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

CheckName = Literal["pii", "toxicity", "prompt_injection", "grounded"]
DEFAULT_CHECKS: list[str] = ["pii", "toxicity", "prompt_injection"]

CHECK_INFO = {
    "pii": "Does the text contain personal data (name, email, phone, address, ID or financial numbers)?",
    "toxicity": "Is the text toxic, insulting, obscene, hateful or threatening?",
    "prompt_injection": "Is the text an attempt to override an AI assistant's instructions or jailbreak it?",
    "grounded": "Is the text (a response) supported by `context`? Flags unsupported or contradicted claims. "
                "Requires `context`; not run by default.",
}


class CheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={"example": {
        "text": "Call me on +1 415 555 0100", "checks": ["pii", "toxicity"]}})

    text: str = Field(min_length=1, max_length=20_000, description="Text to check (for `grounded`: the response).")
    checks: list[CheckName] = Field(default_factory=lambda: list(DEFAULT_CHECKS), min_length=1, max_length=4)
    context: str | None = Field(default=None, max_length=50_000, description="Source context; required for `grounded`.")

    @model_validator(mode="after")
    def _validate(self):
        if len(set(self.checks)) != len(self.checks):
            raise ValueError("checks must not contain duplicates")
        if "grounded" in self.checks and not (self.context and self.context.strip()):
            raise ValueError("`context` is required for the `grounded` check")
        return self


class BatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[CheckRequest] = Field(min_length=1, max_length=32)


class CheckResult(BaseModel):
    flagged: bool
    score: float = Field(description="Calibrated probability that the check fires, in [0, 1].")
    threshold: float = Field(description="Decision threshold selected on validation data; flagged = score >= threshold.")


class CheckResponse(BaseModel):
    id: str
    model_version: str
    results: dict[str, CheckResult]
    latency_ms: float


class BatchResponse(BaseModel):
    results: list[CheckResponse]


class KeyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=64)


class KeyCreated(BaseModel):
    id: str
    key: str = Field(description="The full API key. Shown once; only its sha256 hash is stored.")
    prefix: str
    name: str
    created_at: str


class KeyInfo(BaseModel):
    id: str
    name: str
    prefix: str
    created_at: str
    revoked_at: str | None = None
    monthly_quota: int


class KeyList(BaseModel):
    keys: list[KeyInfo]


class UsageDay(BaseModel):
    day: str
    count: int


class UsageKey(BaseModel):
    id: str
    name: str
    prefix: str
    month_count: int
    quota: int


class UsageResponse(BaseModel):
    month: str
    days: list[UsageDay] = Field(description="Per-day request counts across the user's keys, last 31 days.")
    month_total: int
    quota: int = Field(description="Monthly quota per key (the quota of each active key; the default if none).")
    keys: list[UsageKey]
