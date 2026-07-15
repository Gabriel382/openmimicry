"""``main.py`` — the FastAPI app, lifespan, routes, and WS mount.

This file is intentionally thin. The interesting work happens in
:mod:`openmimicry_backend.wiring`. ``main`` only assembles the FastAPI
surface from the :class:`Wiring` produced there.

Run with::

    uvicorn openmimicry_backend.main:app --reload --port 8000
"""

from __future__ import annotations

import asyncio
import importlib.util
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from openmimicry.core import AppConfig, TaskHandle, UserSpeechFinal
from openmimicry.core.config import load as load_config

from .appearance import load_appearance
from .routes import (
    admin_router,
    appearance_router,
    chat_router,
    dashboard_router,
    health_router,
    mode_router,
    pack_router,
)
from .routes.chat import run_chat_turn
from .wiring import Wiring, build_runtime
from .ws import BroadcastBridge, ws_endpoint

__all__ = ["app", "create_app", "run_uvicorn"]


_log = logging.getLogger(__name__)


def _module_available(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


def _load_app_config() -> tuple[AppConfig, str | None]:
    """Load :class:`AppConfig` from ``OPENMIMICRY_CONFIG_PATH`` or defaults."""
    path_env = os.environ.get("OPENMIMICRY_CONFIG_PATH")
    return load_config(path_env), path_env


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Build the runtime, start the orchestrator + speech, tear it all down."""
    config, config_path = _load_app_config()
    appearance = load_appearance()

    bridge = BroadcastBridge()
    wiring: Wiring = await build_runtime(config, ws_bridge=bridge, config_path=config_path)

    mode_state = {
        "continuous_listening": config.voice.modes.continuous_listening,
        "live_wake": config.voice.modes.live_wake,
        "agent_voice": config.voice.modes.agent_voice,
        "wake_names": list(wiring.speech.wake_names),
    }

    async def _handle_user_text(text: str) -> None:
        await run_chat_turn(
            text,
            bus=wiring.bus,
            llm=wiring.llm,
            tasks=wiring.tasks,
            speech=wiring.speech if mode_state["agent_voice"] else None,
            intent_fn=wiring.intent,
        )

    async def _apply_mode_toggle(key: str, value: bool) -> None:
        if key == "continuous_listening":
            if value:
                await wiring.speech.enable_continuous_listening()
                mode_state["live_wake"] = False
            else:
                await wiring.speech.disable_live_listening()
        elif key == "live_wake":
            if value:
                await wiring.speech.enable_live_listening(wake_names=None)
                mode_state["continuous_listening"] = False
            else:
                await wiring.speech.disable_live_listening()
        elif key == "agent_voice" and not value:
            await wiring.speech.interrupt()
        elif key not in mode_state:
            raise ValueError(f"unknown mode key: {key!r}")
        mode_state[key] = value

    def _mode_status() -> dict[str, object]:
        stt_name = getattr(wiring.stt, "name", "unknown")
        tts_name = getattr(wiring.tts, "name", "unknown")
        real_input = not stt_name.startswith("mock")
        real_output = not tts_name.startswith("mock")
        if stt_name == "realtimestt":
            real_input = _module_available("RealtimeSTT")
        if tts_name == "realtimetts":
            real_output = _module_available("RealtimeTTS")
        return {
            **mode_state,
            "listening_mode": getattr(wiring.speech, "listening_mode", "off"),
            "ptt_active": getattr(wiring.speech, "ptt_active", False),
            "wake_names": list(getattr(wiring.speech, "wake_names", ["Mimi"])),
            "stt_adapter": stt_name,
            "tts_adapter": tts_name,
            "real_input": real_input,
            "real_output": real_output,
            "input_install_hint": (
                None
                if real_input or stt_name.startswith("mock")
                else r"Run .\scripts\win\install.bat openrouter-voice"
            ),
            "output_install_hint": (
                None
                if real_output or tts_name.startswith("mock")
                else r"Run .\scripts\win\install.bat openrouter-voice"
            ),
        }

    async def _cancel_task(raw_handle: dict[str, object]) -> None:
        await wiring.tasks.cancel(TaskHandle.model_validate(raw_handle))

    app.state.wiring = wiring
    app.state.bridge = bridge
    app.state.handle_user_text = _handle_user_text
    app.state.apply_mode_toggle = _apply_mode_toggle
    app.state.mode_state = mode_state
    app.state.appearance = appearance
    app.state.get_mode_status = _mode_status
    app.state.cancel_task = _cancel_task

    speech_subscription = wiring.bus.subscribe()

    async def _consume_speech_turns() -> None:
        async for event in speech_subscription:
            if not isinstance(event, UserSpeechFinal):
                continue
            spoken = event.text.strip()
            if not spoken or event.reason == "interrupted":
                continue
            await _handle_user_text(spoken)

    speech_turn_task = asyncio.create_task(
        _consume_speech_turns(), name="openmimicry.backend.speech_turns"
    )

    await wiring.speech.start()
    if mode_state["continuous_listening"]:
        await wiring.speech.enable_continuous_listening()
    elif mode_state["live_wake"]:
        await wiring.speech.enable_live_listening(wake_names=None)
    await wiring.orchestrator.start()

    _mount_static_characters(app, config)

    try:
        yield
    finally:
        speech_turn_task.cancel()
        with suppress(asyncio.CancelledError, Exception):
            await speech_turn_task
        try:
            await asyncio.wait_for(_graceful_shutdown(wiring), timeout=2.0)
        except TimeoutError:
            _log.warning("backend lifespan: graceful shutdown exceeded 2s budget")


async def _graceful_shutdown(wiring: Wiring) -> None:
    await asyncio.gather(
        wiring.orchestrator.stop(),
        wiring.speech.stop(),
        return_exceptions=True,
    )
    await wiring.runtime.stop()


def create_app() -> FastAPI:
    app = FastAPI(
        title="OpenMimicry Backend",
        version="1.3.0",
        lifespan=lifespan,
    )

    app.include_router(health_router)
    app.include_router(chat_router)
    app.include_router(dashboard_router)
    app.include_router(mode_router)
    app.include_router(pack_router)
    app.include_router(admin_router)
    app.include_router(appearance_router)

    @app.websocket("/ws")
    async def _ws(websocket: WebSocket) -> None:
        wiring: Wiring = websocket.app.state.wiring
        bridge: BroadcastBridge = websocket.app.state.bridge
        handle_user_text = websocket.app.state.handle_user_text
        apply_mode_toggle = websocket.app.state.apply_mode_toggle
        get_mode_status = websocket.app.state.get_mode_status
        cancel_task = websocket.app.state.cancel_task
        await ws_endpoint(
            websocket,
            bus=wiring.bus,
            speech=wiring.speech,
            bridge=bridge,
            handle_user_text=handle_user_text,
            apply_mode_toggle=apply_mode_toggle,
            get_mode_status=get_mode_status,
            cancel_task=cancel_task,
        )

    return app


app = create_app()


def _mount_static_characters(app: FastAPI, config: AppConfig) -> None:
    """Mount the first existing ``avatar.pack_roots`` entry at ``/static/characters``."""
    for raw in config.avatar.pack_roots:
        root = Path(raw).expanduser()
        if root.is_dir():
            try:
                app.mount(
                    "/static/characters",
                    StaticFiles(directory=str(root)),
                    name="characters",
                )
            except Exception as exc:
                _log.warning("static-mount /static/characters failed: %s", exc)
            return
    _log.info("no avatar.pack_roots directory found; skipping static mount")


def run_uvicorn() -> None:  # pragma: no cover - script entry point
    """`openmimicry-backend` console script."""
    import uvicorn

    host = os.environ.get("OPENMIMICRY_HOST", "127.0.0.1")
    port = int(os.environ.get("OPENMIMICRY_PORT", "8000"))
    uvicorn.run(
        "openmimicry_backend.main:app",
        host=host,
        port=port,
        reload=False,
    )
