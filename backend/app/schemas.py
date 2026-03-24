
from __future__ import annotations
from pydantic import BaseModel
from typing import Optional

class ChatRequest(BaseModel):
    text: str
    character: Optional[str] = None

class AvatarDirective(BaseModel):
    emotion: str
    animation: str
    speaking: bool = False
    next_state: str = "idle"
    duration_ms: Optional[int] = None

class ChatResponse(BaseModel):
    text: str
    backend: str
    avatar: AvatarDirective

class HealthResponse(BaseModel):
    ok: bool
    provider: str
    message: str

class TTSRequest(BaseModel):
    text: str
    preferred_adapter: Optional[str] = None
