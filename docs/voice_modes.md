# Voice modes, interruptible TTS, and barge-in

OpenMimicry supports text, push-to-talk, name-gated hands-free input, optional
ungated continuous input, and agent voice. The everyday controls live on the avatar's
top toolbar and in the local browser dashboard.

```yaml
voice:
  modes:
    text_always_on: true     # /chat input box always usable; never disables
    push_to_talk_hotkey: "Ctrl+Space"
    continuous_listening: false  # advanced: submit every final utterance
    live_wake: false         # toolbar: require a configured name prefix
    agent_voice: true        # speak LLM replies via TTS
    barge_in_grace_ms: 600
```

## 1. Input and output modes

**Text always on.** The toolbar and browser-dashboard inputs do not depend on
the voice subsystem. If STT/TTS are broken, text still works.

**Push-to-talk.** Hold the toolbar microphone or `Ctrl+Space`. The microphone
is open only for the press duration. On release, the final transcript is sent
as a chat turn. If passive listening is active, it pauses for PTT and is restored
after release so only one consumer reads the STT stream.

**Wake listen (`live_wake`).** RealtimeSTT stays in dictation mode and uses
voice activity detection to wait for speech. `SpeechController` submits a final
utterance only when it begins with a configured name such as “Mimi” or “Hey
Mimi”; the matching prefix and punctuation are removed from the command. The
toolbar exposes this as the safe hands-free option. Change the name in the
local dashboard; it is saved to `config/user.yaml`.

**Continuous listening (`continuous_listening`).** This advanced API/config
mode submits every final utterance without requiring a name. It remains useful
for controlled environments but is not the normal toolbar control.

**Agent voice.** When on, LLM replies are streamed into TTS (token-by-token, low-latency). When off, replies are only displayed in the speech bubble. Off does not impose any cost: the TTS adapter is not started.

The user can run pure text, voice-out only, PTT input, or name-gated hands-free
listening. PTT and passive listening coordinate atomically around one microphone.

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
- Disabling continuous or wake listening shuts STT cleanly.
- PTT pauses and restores continuous listening without leaving stale queue
  sentinels or competing transcript consumers.

All of those use the mock adapters; no audio hardware is required in CI.
