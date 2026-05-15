
# OpenMimicry Milestone 8 — Voice interaction modes

This bundle adds a practical starter for:
- live wake mode
- push-to-talk mode
- voice output enable/disable
- interruptible TTS
- voice state machine
- STT/TTS adapter interfaces
- VAD-based speech capture inspired by the uploaded `speech_to_text.py`
- pyttsx3-based TTS fallback inspired by the uploaded `text_to_speech.py`

## Main additions
- `backend/app/voice_state.py`
- `backend/app/stt_*`
- `backend/app/voice_controller.py`
- `backend/app/tts_router.py` update with stop support
- `frontend/src/voice/*`
- updated `frontend/src/pages/OverlayApp_voice_patch.tsx`
- config additions in `config/runtime.yml` and `characters/octomimic/character.yml`
