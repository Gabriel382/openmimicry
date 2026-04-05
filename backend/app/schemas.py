
from __future__ import annotations
from pydantic import BaseModel
from typing import Optional

class ChatRequest(BaseModel):
    text: str

class AvatarDirective(BaseModel):
    emotion: str
    animation: str
    speaking: bool = False
    next_state: str = "idle"

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
