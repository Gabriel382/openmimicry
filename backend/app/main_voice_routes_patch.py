
from app.voice_controller import voice_controller
from app.voice_models import VoiceToggleRequest, VoicePTTRequest

@app.get("/voice/status")
def voice_status():
    return voice_controller.status()

@app.post("/voice/live-wake")
def voice_live_wake(req: VoiceToggleRequest):
    return voice_controller.set_live_wake(req.enabled)

@app.post("/voice/push-to-talk-mode")
def voice_push_to_talk_mode(req: VoiceToggleRequest):
    return voice_controller.set_push_to_talk_mode(req.enabled)

@app.post("/voice/agent-voice")
def voice_agent_voice(req: VoiceToggleRequest):
    return voice_controller.set_agent_voice(req.enabled)

@app.post("/voice/ptt")
def voice_ptt(req: VoicePTTRequest):
    if req.action == "start":
        return voice_controller.ptt_start()
    if req.action == "stop":
        return voice_controller.ptt_stop_and_transcribe()
    return {"error": "unsupported action"}

@app.post("/voice/interrupt")
def voice_interrupt():
    voice_controller.interrupt_output()
    return {"ok": True}
