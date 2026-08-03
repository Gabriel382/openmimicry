# OpenMimicry v1.8.2 release notes

Version 1.8.2 fixes two interaction regressions reported against v1.8.1.

## White thinking balloon

Thinking is again displayed in a white, accent-bordered balloon above the
avatar. It is not rendered in the red toolbar banner. The balloon:

- appears for an admitted text, push-to-talk, continuous, or wake turn;
- remains visible while the LLM is processing;
- disappears when reply text or prepared audio begins;
- disappears on completed, failed, or cancelled turns.

The red toolbar banner is now limited to voice failures, backend failures, and
terminal turn errors. Backend refresh uses a neutral status style.

## Hung OpenRouter response recovery

The configured `request_timeout_s` now applies to the whole LiteLLM operation:
opening the request and consuming every streamed chunk. Previously, a provider
could open a stream and then stop yielding, bypassing its transport timeout.

When the deadline is exceeded:

1. an actionable LLM timeout is published;
2. the turn reaches the terminal `failed` state;
3. the single-flight lease is released;
4. the avatar exits thinking;
5. the next text or voice turn can be submitted without restarting.

The timeout remains configurable per backend. The integrated OpenRouter
profile uses 90 seconds.

## Upgrade

Install the normal profile and launch with the existing command:

```powershell
.\scripts\win\install.bat openrouter-chatterbox
powershell -ExecutionPolicy Bypass -File .\scripts\win\start-openrouter-voice.ps1
```

No voice-model redownload or special repair script is required.
