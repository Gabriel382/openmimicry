
# OpenMimicry UI Redesign Starter

This starter bundle includes:
- modern React frontend intended for Tauri
- separate overlay and control panel surfaces
- YAML-driven theme, runtime, personality, and character config
- FastAPI backend
- LLM adapter layer
- TTS adapter stack with fallback ordering
- character packs using `emotion` and `emotion_speaking` folders

## TTS fallback order
1. browser/system voice in frontend
2. Piper adapter in backend if configured
3. pyttsx3 adapter in backend
4. noop fallback

## Run

Backend:
```bash
cd backend
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Frontend:
```bash
cd frontend
npm install
npm install --save-dev @tauri-apps/cli@latest
npm run dev
```
