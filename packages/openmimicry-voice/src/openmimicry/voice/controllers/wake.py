"""``WakeController`` — thin enable/disable wrapper around an STT in wake mode.

Most projects will use :class:`SpeechController.enable_live_listening` /
``disable_live_listening`` directly; the WakeController exists for callers
that want a dedicated, single-purpose object (e.g. a Tauri tray-menu
toggle) and for the contract test surface.
"""

from __future__ import annotations

from openmimicry.core.contracts import STTAdapter
from openmimicry.core.schemas import STTConfig
from openmimicry.core.schemas.app import STTConfigSection

__all__ = ["WakeController"]


class WakeController:
    """Toggle for an STT in ``mode="wake"`` listening state."""

    def __init__(
        self,
        *,
        stt: STTAdapter,
        config: STTConfigSection | None = None,
    ) -> None:
        self._stt = stt
        self._cfg = config or STTConfigSection()
        self._enabled: bool = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    async def enable(self) -> None:
        if self._enabled:
            return
        await self._stt.start(
            STTConfig(
                language=self._cfg.language,
                mode="wake",
                wake_names=list(self._cfg.wake.names),
                sample_rate=self._cfg.sample_rate,
                vad=self._cfg.vad,
            )
        )
        self._enabled = True

    async def disable(self) -> None:
        if not self._enabled:
            return
        self._enabled = False
        await self._stt.stop()
