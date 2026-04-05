
from __future__ import annotations
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import load_theme, load_runtime, load_personality, load_character
from app.schemas import ChatRequest, ChatResponse, HealthResponse, TTSRequest
from app.router import build_llm, ask
from app.director import decide_avatar
from app.tts_router import speak_with_fallback

ROOT = Path(__file__).resolve().parents[2]

app = FastAPI(title="OpenMimicry Backend")
app.mount("/static", StaticFiles(directory=str(ROOT)), name="static")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/config")
def config():
    runtime = load_runtime()
    character_name = runtime.get("ui", {}).get("active_character", "octomimic")
    return {
        "theme": load_theme(),
        "runtime": runtime,
        "personality": load_personality(),
        "character": load_character(character_name),
    }

@app.get("/health", response_model=HealthResponse)
def health():
    llm = build_llm()
    ok, msg = llm.health()
    return HealthResponse(ok=ok, provider=llm.name, message=msg)

@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    backend_name, text = ask(req.text)
    avatar = decide_avatar(text)
    return ChatResponse(text=text, backend=backend_name, avatar=avatar)

@app.post("/tts")
def tts(req: TTSRequest):
    adapter, ok = speak_with_fallback(req.text, preferred=req.preferred_adapter)
    return {"ok": ok, "adapter": adapter}
