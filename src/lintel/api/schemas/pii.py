"""PII response models."""

from pydantic import BaseModel


class RevealPIICommandResponse(BaseModel):
    model_config = {"extra": "allow"}

    thread_ref: dict[str, str] = {}
    placeholder: str = ""
    requester_id: str = ""
    reason: str = ""


class VaultLogEntry(BaseModel):
    action: str
    placeholder: str
    requester_id: str
    reason: str
    thread_ref: dict[str, str]
    timestamp: str


class PiiStatsResponse(BaseModel):
    total_scanned: int = 0
    total_detected: int = 0
    total_anonymised: int = 0
    total_blocked: int = 0
    total_reveals: int = 0
