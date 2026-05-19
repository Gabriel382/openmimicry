"""``main.py`` — the FastAPI app, lifespan, routes, and WS mount.

This file is intentionally thin. The interesting work happens in
:mod:`openmimicry_backend.wiring`. ``main`` only assembles the FastAPI
surface from the :class:`Wiring` produced there.

Run with::

    uvicorn openmimicry_backend.main:app --reload --port 8000
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from openmimicry.core import AppConfig
from openmimicry.core.config import load as load_config

from .routes import (
    admin_router,
    chat_router,
    health_router,
    mode_router,
    pack_router,
)
from .routes.chat import run_chat_turn
from .wiring import Wiring, build_runtime
from .ws import BroadcastBridge, ws_endpoint

__all__ = ["app", "create_app", "run_uvicorn"]


_log = logging.getLogger(__name__)


def _load_app_config() -> tuple[AppConfig, str | None]:
    """Load :class:`AppConfig` from ``OPENMIMICRY_CONFIG_PATH`` or defaults."""
    path_env = os.environ.get("OPENMIMICRY_CONFIG_PATH")
    if path_env:
        return load_config(path_env), path_env
    return AppConfig(), None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Build the runtime, start the orchestrator + speech, tear it all down."""
    config, config_path = _load_app_config()

    bridge = BroadcastBridge()
    wiring: Wiring = await build_runtime(
        config, ws_bridge=bridge, config_path=config_path
    )

    async def _handle_user_text(text: str) -> None:
        await run_chat_turn(
            text,
            bus=wiring.bus,
            llm=wiring.llm,
            tasks=wiring.tasks,
            speech=wiring.speech,
            intent_fn=wiring.intent,
        )

    async def _apply_mode_toggle(key: str, value: bool) -> None:
        if key == "live_wake":
            if value:
                await wiring.speech.enable_live_listening(wake_names=None)
            else:
                await wiring.speech.disable_live_listening()
        elif key == "agent_voice" and not value:
            await wiring.speech.interrupt()

    app.state.wiring = wiring
    app.state.bridge = bridge
    app.state.handle_user_text = _handle_user_text
    app.state.apply_mode_toggle = _apply_mode_toggle

    await wiring.speech.start()
    await wiring.orchestrator.start()

    _mount_static_characters(app, config)

    try:
        yield
    finally:
        try:
            await asyncio.wait_for(_graceful_shutdown(wiring), timeout=2.0)
        except asyncio.TimeoutError:
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
        version="0.2.0a0",
        lifespan=lifespan,
    )

    app.include_router(health_router)
    app.include_router(chat_router)
    app.include_router(mode_router)
    app.include_router(pack_router)
    app.include_router(admin_router)

    @app.websocket("/ws")
    async def _ws(websocket: WebSocket) -> None:
        wiring: Wiring = websocket.app.state.wiring
        bridge: BroadcastBridge = websocket.app.state.bridge
        handle_user_text = websocket.app.state.handle_user_text
        apply_mode_toggle = websocket.app.state.apply_mode_toggle
        await ws_endpoint(
            websocket,
            bus=wiring.bus,
            speech=wiring.speech,
            bridge=bridge,
            handle_user_text=handle_user_text,
            apply_mode_toggle=apply_mode_toggle,
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
            except Exception as exc:  # noqa: BLE001
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
