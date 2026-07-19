"""Direct ElevenLabs HTTP TTS adapter; no provider SDK dependency."""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
import wave
from collections.abc import AsyncIterable
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from openmimicry.core.schemas import TTSConfig

from .system_command import _collect_text, _playback_command

__all__ = ["ElevenLabsSettings", "ElevenLabsTTSAdapter"]


_MAX_AUDIO_BYTES = 64 * 1024 * 1024


@dataclass(frozen=True)
class ElevenLabsSettings:
    voice_id: str
    api_key_env: str = "ELEVENLABS_API_KEY"
    model_id: str = "eleven_multilingual_v2"
    endpoint: str = "https://api.elevenlabs.io"


class ElevenLabsTTSAdapter:
    name = "elevenlabs"

    def __init__(self, settings: ElevenLabsSettings) -> None:
        self._settings = settings
        self._session_api_key: str | None = None
        self._process: asyncio.subprocess.Process | None = None
        self._ready = asyncio.Event()
        self._is_speaking = False

    def set_session_api_key(self, value: str) -> None:
        token = value.strip()
        if not token or len(token) > 8192:
            raise ValueError("ElevenLabs token must contain 1 to 8192 characters")
        self._session_api_key = token

    def clear_session_api_key(self) -> None:
        self._session_api_key = None

    @property
    def has_session_api_key(self) -> bool:
        return self._session_api_key is not None

    @property
    def has_credentials(self) -> bool:
        return self.has_session_api_key or bool(os.environ.get(self._settings.api_key_env))

    def credential_status(self) -> dict[str, bool]:
        """Expose credential sources without exposing either credential."""

        return {
            "session": self.has_session_api_key,
            "environment": bool(os.environ.get(self._settings.api_key_env)),
        }

    def _api_key(self) -> str:
        key = self._session_api_key or os.environ.get(self._settings.api_key_env)
        if not key:
            raise RuntimeError(
                f"ElevenLabs requires {self._settings.api_key_env} or a session-only token"
            )
        return key

    async def prepare(self, _config: TTSConfig) -> None:
        self._api_key()
        with tempfile.TemporaryDirectory() as tmp:
            _playback_command(Path(tmp) / "preflight.wav")

    async def speak(
        self,
        text_or_stream: str | AsyncIterable[str],
        *,
        config: TTSConfig,
        on_chunk=None,
    ) -> None:
        text = await _collect_text(text_or_stream)
        if not text.strip():
            return
        if len(text) > 10_000:
            raise ValueError("ElevenLabs multilingual v2 input exceeds 10,000 characters")
        await self.stop()
        self._ready = asyncio.Event()
        self._is_speaking = True
        try:
            pcm = await asyncio.to_thread(self._synthesize, text)
            with tempfile.TemporaryDirectory(prefix="openmimicry-elevenlabs-") as tmp:
                wave_path = Path(tmp) / "utterance.wav"
                _write_pcm_wave(wave_path, pcm, sample_rate=24000)
                command, environment = _playback_command(wave_path)
                self._process = await asyncio.create_subprocess_exec(
                    *command,
                    env=environment,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.PIPE,
                )
                self._ready.set()
                _stdout, stderr = await self._process.communicate()
                if self._process.returncode not in {0, None}:
                    raise RuntimeError(
                        "ElevenLabs audio playback failed: "
                        + stderr.decode("utf-8", errors="replace")[-1000:]
                    )
        finally:
            self._process = None
            self._is_speaking = False

    def _synthesize(self, text: str) -> bytes:
        voice_id = quote(self._settings.voice_id, safe="")
        endpoint = self._settings.endpoint.rstrip("/")
        url = f"{endpoint}/v1/text-to-speech/{voice_id}?output_format=pcm_24000"
        body = json.dumps({"text": text, "model_id": self._settings.model_id}).encode()
        request = Request(
            url,
            data=body,
            headers={
                "Accept": "application/octet-stream",
                "Content-Type": "application/json",
                "User-Agent": "OpenMimicry/1.6",
                "xi-api-key": self._api_key(),
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=90.0) as response:
                audio = response.read(_MAX_AUDIO_BYTES + 1)
        except HTTPError as exc:
            detail = exc.read(2048).decode("utf-8", errors="replace")
            raise RuntimeError(f"ElevenLabs returned HTTP {exc.code}: {detail}") from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise RuntimeError(f"ElevenLabs request failed: {exc}") from exc
        if len(audio) > _MAX_AUDIO_BYTES:
            raise RuntimeError("ElevenLabs audio response exceeded 64 MiB")
        if not audio:
            raise RuntimeError("ElevenLabs returned an empty audio response")
        return audio

    async def wait_until_ready(self, *, timeout_s: float = 30.0) -> bool:
        try:
            async with asyncio.timeout(timeout_s):
                await self._ready.wait()
            return True
        except TimeoutError:
            return False

    async def stop(self) -> None:
        process = self._process
        if process is None or process.returncode is not None:
            return
        process.terminate()
        with suppress(Exception):
            async with asyncio.timeout(1.0):
                await process.wait()
        if process.returncode is None:
            process.kill()

    @property
    def is_speaking(self) -> bool:
        return self._is_speaking

    async def healthcheck(self) -> bool:
        try:
            self._api_key()
        except RuntimeError:
            return False
        return True

    async def close(self) -> None:
        await self.stop()


def _write_pcm_wave(path: Path, pcm: bytes, *, sample_rate: int) -> None:
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(pcm)
