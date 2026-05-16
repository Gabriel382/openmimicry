# Voice modes, interruptible TTS, and barge-in

OpenMimicry supports four orthogonal voice toggles. They are configured under `voice.modes` and can be flipped at runtime through the panel UI.

```yaml
voice:
  modes:
    text_always_on: true     # /chat input box always usable; never disables
    push_to_talk_hotkey: "Ctrl+Space"
    live_wake: true          # passive wake-word listening
    agent_voice: true        # speak LLM replies via TTS
    barge_in_grace_ms: 600
```

## 1. The four modes

**Text always on.** The panel's text input is always wired straight to `Runtime.handle_user_text(text)`. It does not depend on the voice subsystem being healthy. If STT/TTS are broken, text still works.

**Push-to-talk.** A global hotkey (Tauri-registered for cross-window capture) opens the mic for the duration of the keypress. While held, all running TTS is cancelled. On release, the final transcript is dispatched as if the user had typed it. PTT works regardless of `live_wake`.

**Live wake.** STT runs continuously in low-cost wake-listening mode. On a wake word, the controller switches the STT to dictation mode, the avatar enters `listening`, and the flow proceeds as PTT. Wake names are configurable; multiple are supported.

**Agent voice.** When on, LLM replies are streamed into TTS (token-by-token, low-latency). When off, replies are only displayed in the speech bubble. Off does not impose any cost: the TTS adapter is not started.

These toggles compose. The user can run pure-text, voice-out only, voice-in only via PTT, or fully hands-free.

## 2. Interruptible TTS

Interruptibility is a TTS-adapter capability and a `SpeechController` responsibility.

Adapter requirement: the `TTSAdapter.stop()` method must cancel both playback and the underlying speech generator within ~100 ms. RealtimeTTS supports this via its stream/queue abstractions; the wrapper exposes a single cancel flag the loop checks per chunk.

Controller invariant: at most one `TTSAdapter.speak(...)` task is alive at a time. `SpeechController.say(...)` is:

```python
async def say(self, text_or_stream):
    if self._current is not None and not self._current.done():
        await self.interrupt()
    self._current = asyncio.create_task(
        self._tts.speak(text_or_stream, config=self._cfg.tts, on_chunk=self._on_chunk)
    )
    self.bus.publish(TTSStarted())
    try:
        await self._current
        self.bus.publish(TTSFinished())
    except CancelledError:
        self.bus.publish(TTSInterrupted())
```

`interrupt()` calls `self._tts.stop()` and awaits the task. Anything that creates a new utterance (a new user message, a PTT press, a wake detection) goes through `say` or `interrupt` and never touches `_tts` directly.

## 3. Barge-in

Barge-in is "user starts speaking while the avatar is speaking." It needs three things to feel natural:

- **Low-latency detection.** The STT runs even while TTS is playing. RealtimeSTT's VAD fires `speech_start` events well before a full transcript is ready.
- **Mic safety.** A talking speaker can falsely trigger the VAD. We avoid building our own echo canceller. Instead:
  - Recommend a USB/cardioid mic in the README.
  - Enable RealtimeSTT's echo handling where supported.
  - Provide `voice.modes.barge_in_grace_ms` (default 600 ms): the controller must receive `speech_start` *for at least this long* before it cancels TTS. Tunes out short echo bursts.
- **Single owner.** Only `SpeechController` decides to cancel TTS. The avatar director does not. The LLM does not. This avoids races.

```python
class SpeechController:
    async def _on_vad_speech_start(self):
        if not self._cfg.tts.interruptible:
            return
        if not self._tts.is_speaking:
            # User is just talking; nothing to interrupt.
            return
        await asyncio.sleep(self._cfg.modes.barge_in_grace_ms / 1000)
        # Re-check after the grace window — VAD may have settled.
        if self._stt.vad_active and self._tts.is_speaking:
            await self.interrupt()
            self.bus.publish(UserSpeechStarted())
```

The avatar's reaction to barge-in is whatever it is for `UserSpeechStarted` (transition to `listening`). The director does not know barge-in happened; it just reacts to the event. That's the point of the abstraction.

## 4. Mode transitions are atomic from the frontend's view

The frontend never sees half-states. The only signals it gets are:

- `AvatarDirective` (one at a time, replaces previous),
- `TranscriptPreview` (text frame for the speech bubble),
- `SpeechBubbleText` (assistant reply progress),
- `SystemNotice` (mode toggles, errors).

If TTS is interrupted mid-reply, the frontend sees `TTSInterrupted` -> `AvatarDirective(listening)`; the bubble keeps the partial text. There is no "TTSInterrupted but still speaking" intermediate state.

## 5. Test coverage

`tests/integration/test_voice_modes.py` covers:

- `say` cancels and replaces a running utterance.
- `ptt_down` cancels TTS within 100 ms.
- `WakeDetected` while TTS plays causes `TTSInterrupted` then `listening`.
- VAD bounces shorter than `barge_in_grace_ms` do not cancel TTS.
- Disabling `agent_voice` mid-reply stops at the next chunk boundary and emits `TTSFinished`, not `TTSInterrupted`.
- Disabling `live_wake` while listening shuts STT cleanly.

All of those use the mock adapters; no audio hardware is required in CI.
