# Voice providers and cloning

OpenMimicry v1.6 separates the supported commercial dependency path from
opt-in community and cloud voice paths. All providers implement the same
speech lifecycle, and every failure must release the avatar state and leave
typed chat usable.

## Provider matrix

| Adapter | Price path | Where synthesis runs | First-use behavior | Intended profile |
|---|---|---|---|---|
| `system-command` | Free | Host OS speech facility | No model download | commercial default |
| `isolated-piper` | Free | Disposable local child process | Voice download/preflight | community Piper |
| `chatterbox-local` | Free | Persistent isolated ML worker | Large model load; prewarmed | community cloning |
| `elevenlabs` | Provider credits/BYOK | ElevenLabs HTTPS | Account/voice must exist | cloud opt-in |

The local Chatterbox path is the no-credit voice-cloning option. It needs
sufficient RAM/compute and a reference WAV/MP3 for a speaker who has explicitly
consented. The model process is prewarmed once and reused, but remains outside
FastAPI so a crash or cancellation can be contained and restarted.

## Configure local cloning

1. Install through the ordinary profile mechanism: on Windows run
   `.\scripts\win\install.bat openrouter-chatterbox`; on Linux/macOS run
   `make install PROFILE=openrouter-chatterbox`.
2. Allow the hardware check to complete. The installer selects official Torch
   2.6 CUDA wheels for compatible NVIDIA
   drivers, Apple MPS on macOS, or CPU when no accelerator is available.
3. Open the dashboard and upload a short, clean reference recording under the
   voice-cloning settings.
4. Enter a dated consent record identifying the permission you obtained.
5. On Windows, start voice exactly as for Piper:
   `powershell -ExecutionPolicy Bypass -File .\scripts\win\start-openrouter-voice.ps1`.
   The launcher detects the dashboard selection. On Linux/macOS, run
   `OPENMIMICRY_PROFILE=openrouter-chatterbox make backend`.

Uploaded audio is limited to 20 MiB, must have a WAV or MP3 signature, is
created with private permissions, and is stored in the user data directory.
If the settings transaction fails, the newly written reference is deleted.

Automatic device selection preserves an already verified CUDA triplet, then
selects CUDA, Apple MPS, or CPU as appropriate. Chatterbox
is a large experimental ML profile; validate it on each target OS/hardware
combination before claiming support.

OpenMimicry applies the Chatterbox 0.1.7/NumPy 2 reference-audio float32
compatibility correction inside the disposable worker. It never edits the
installed Chatterbox package. The worker handshake records Torch, CUDA, NumPy,
device, and compatibility status in ordinary diagnostics. HTTP health checks
only inspect an already-prepared worker and never initiate a cold model load.

The profile installer also verifies the real Perth watermark constructor. The
PyPI 1.0.1 package can hide an internal import failure by exposing a `None`
constructor; when that exact condition is found, OpenMimicry installs official
Perth commit `ce86c49d029f42272c1902eccb675556b9ed2330` from its immutable
archive without reinstalling dependencies. Worker startup refuses to use
Perth's dummy watermarker and reports the original import cause if the repair
cannot produce the real implementation.

## Configure ElevenLabs

Create/select the voice in the user's ElevenLabs account, set
`ELEVENLABS_API_KEY` in the environment (or provide a process-only session
token through the local dashboard), and save the voice ID plus consent record. OpenMimicry
does not upload a training/reference recording to ElevenLabs and never writes
the API key to user YAML.

## Reply presentation

Choose in the dashboard:

- `parallel`: show text immediately and start speech concurrently.
- `voice_ready`: reveal text only when matching speech is ready; on bounded
  failure, show text as a fallback.
- `text_only`: never queue speech.
- `voice_only`: keep text in history/accessibility surfaces but hide the
  avatar bubble.

For visible text, the dismissal deadline is `base + characters ×
milliseconds-per-character`, clamped by minimum/maximum. The bubble remains
until both that deadline and the matching TTS terminal event have occurred.

## Safety and licensing

Only clone voices with informed permission. A typed consent note is a product
guardrail, not legal proof. Review `docs/licensing.md`: the Piper application
and voice models, Chatterbox dependency/model artifacts, and cloud-provider
terms have distinct distribution implications.
