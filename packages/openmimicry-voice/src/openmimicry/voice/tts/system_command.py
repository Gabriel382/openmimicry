"""Dependency-free TTS through allow-listed operating-system commands."""

from __future__ import annotations

import asyncio
import os
import platform
import shutil
import tempfile
from collections.abc import AsyncIterable
from contextlib import suppress
from pathlib import Path

from openmimicry.core.schemas import TTSConfig

__all__ = ["SystemCommandTTSAdapter", "SystemTTSUnavailable"]


class SystemTTSUnavailable(RuntimeError):
    pass


class SystemCommandTTSAdapter:
    """Speak with Windows System.Speech, macOS ``say``, or Linux espeak-ng.

    Every subprocess uses an argv list and fixed script text. User/LLM text is
    passed through a temporary UTF-8 file, never interpolated into a shell.
    """

    name = "system-command"

    def __init__(self) -> None:
        self._process: asyncio.subprocess.Process | None = None
        self._ready = asyncio.Event()
        self._is_speaking = False
        self._closed = False

    async def prepare(self, _config: TTSConfig) -> None:
        _commands()

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
        await self.stop()
        self._ready = asyncio.Event()
        self._is_speaking = True
        try:
            with tempfile.TemporaryDirectory(prefix="openmimicry-tts-") as raw_tmp:
                tmp = Path(raw_tmp)
                text_path = tmp / "utterance.txt"
                wave_path = tmp / "utterance.wav"
                text_path.write_text(text, encoding="utf-8")
                synth, play, environment = _commands(
                    text_path=text_path,
                    wave_path=wave_path,
                    rate=config.rate,
                )
                await _run_checked(synth, environment=environment)
                self._process = await asyncio.create_subprocess_exec(
                    *play,
                    env=environment,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.PIPE,
                )
                self._ready.set()
                _stdout, stderr = await self._process.communicate()
                if self._process.returncode not in {0, None}:
                    message = stderr.decode("utf-8", errors="replace")[-1000:]
                    raise SystemTTSUnavailable(f"audio playback failed: {message}")
        finally:
            self._process = None
            self._is_speaking = False

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
        with suppress(ProcessLookupError, TimeoutError):
            async with asyncio.timeout(1.0):
                await process.wait()
        if process.returncode is None:
            process.kill()
            with suppress(Exception):
                await process.wait()

    @property
    def is_speaking(self) -> bool:
        return self._is_speaking

    async def healthcheck(self) -> bool:
        if self._closed:
            return False
        try:
            _commands()
        except SystemTTSUnavailable:
            return False
        return True

    async def close(self) -> None:
        await self.stop()
        self._closed = True


async def _collect_text(value: str | AsyncIterable[str]) -> str:
    if isinstance(value, str):
        return value
    parts: list[str] = []
    async for part in value:
        parts.append(part)
    return "".join(parts)


def _commands(
    *,
    text_path: Path | None = None,
    wave_path: Path | None = None,
    rate: float = 1.0,
) -> tuple[list[str], list[str], dict[str, str]]:
    system = platform.system()
    environment = dict(os.environ)
    if system == "Windows":
        powershell = shutil.which("powershell") or shutil.which("pwsh")
        if not powershell:
            raise SystemTTSUnavailable("PowerShell is required for system TTS")
        if text_path is None or wave_path is None:
            return [powershell], [powershell], environment
        environment["OPENMIMICRY_TEXT_PATH"] = str(text_path)
        environment["OPENMIMICRY_WAV_PATH"] = str(wave_path)
        environment["OPENMIMICRY_SPEECH_RATE"] = str(max(-10, min(10, round((rate - 1) * 5))))
        synth_script = (
            "Add-Type -AssemblyName System.Speech; "
            "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            "$s.Rate=[int]$env:OPENMIMICRY_SPEECH_RATE; "
            "$s.SetOutputToWaveFile($env:OPENMIMICRY_WAV_PATH); "
            "$s.Speak([IO.File]::ReadAllText($env:OPENMIMICRY_TEXT_PATH)); $s.Dispose()"
        )
        common = [powershell, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass"]
        play, playback_environment = _playback_command(wave_path)
        environment.update(playback_environment)
        return [*common, "-Command", synth_script], play, environment

    if system == "Darwin":
        say = shutil.which("say")
        afplay = shutil.which("afplay")
        if not say or not afplay:
            raise SystemTTSUnavailable("macOS say and afplay commands are required")
        if text_path is None or wave_path is None:
            return [say], [afplay], environment
        words_per_minute = str(max(80, min(450, round(180 * rate))))
        play, playback_environment = _playback_command(wave_path)
        environment.update(playback_environment)
        return (
            [say, "-r", words_per_minute, "-o", str(wave_path), "-f", str(text_path)],
            play,
            environment,
        )

    espeak = shutil.which("espeak-ng") or shutil.which("espeak")
    player = shutil.which("aplay") or shutil.which("paplay")
    if not espeak or not player:
        raise SystemTTSUnavailable("Linux system TTS requires espeak-ng and aplay/paplay")
    if text_path is None or wave_path is None:
        return [espeak], [player], environment
    words_per_minute = str(max(80, min(450, round(175 * rate))))
    play, playback_environment = _playback_command(wave_path)
    environment.update(playback_environment)
    return (
        [espeak, "-s", words_per_minute, "-f", str(text_path), "-w", str(wave_path)],
        play,
        environment,
    )


def _playback_command(wave_path: Path) -> tuple[list[str], dict[str, str]]:
    environment = dict(os.environ)
    system = platform.system()
    if system == "Windows":
        powershell = shutil.which("powershell") or shutil.which("pwsh")
        if not powershell:
            raise SystemTTSUnavailable("PowerShell is required for wave playback")
        environment["OPENMIMICRY_WAV_PATH"] = str(wave_path)
        script = (
            "$p=New-Object System.Media.SoundPlayer($env:OPENMIMICRY_WAV_PATH); "
            "$p.PlaySync(); $p.Dispose()"
        )
        return (
            [
                powershell,
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                script,
            ],
            environment,
        )
    if system == "Darwin":
        player = shutil.which("afplay")
    else:
        player = shutil.which("aplay") or shutil.which("paplay")
    if not player:
        raise SystemTTSUnavailable("no supported wave playback command was found")
    return [player, str(wave_path)], environment


async def _run_checked(command: list[str], *, environment: dict[str, str]) -> None:
    process = await asyncio.create_subprocess_exec(
        *command,
        env=environment,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _stdout, stderr = await process.communicate()
    if process.returncode != 0:
        message = stderr.decode("utf-8", errors="replace")[-1000:]
        raise SystemTTSUnavailable(f"speech synthesis failed: {message}")
