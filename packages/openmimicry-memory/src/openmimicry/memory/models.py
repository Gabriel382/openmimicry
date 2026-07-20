"""Frozen memory records shared by every provider."""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field

__all__ = ["MemoryCandidate", "MemoryRecord"]


class MemoryCandidate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    subject: str = Field(default="user", min_length=1, max_length=128)
    predicate: str = Field(min_length=1, max_length=128)
    value: str = Field(min_length=1, max_length=2048)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class MemoryRecord(MemoryCandidate):
    id: str
    source: str = "conversation"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
