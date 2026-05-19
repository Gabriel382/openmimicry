"""Integration fixtures for the M6 FastAPI backend.

The fixture pipeline is:

1. Load ``tests/fixtures/configs/integration.yaml`` -> an :class:`AppConfig`
   whose every adapter is a mock.
2. Build a :class:`Wiring` via ``build_runtime`` with a real
   :class:`BroadcastBridge`.
3. Hand the FastAPI app's ``TestClient`` to the test plus a few accessors
   onto the controllers tests need to drive (``mock_llm``, ``mock_stt``,
   ``mock_tts``, ``mock_tasks``).

The lifespan-attached state is replaced with the test wiring before
the TestClient opens its first connection so routes see the same wiring
the tests inspect.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from openmimicry.core.config import load as load_config
from openmimicry.core.schemas.app import AppConfig
from openmimicry_backend.main import create_app
from openmimicry_backend.routes.chat import run_chat_turn
from openmimicry_backend.wiring import Wiring, build_runtime
from openmimicry_backend.ws import BroadcastBridge

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"


@pytest.fixture
def integration_config(monkeypatch: pytest.MonkeyPatch) -> AppConfig:
    """Load the integration YAML in env-isolation."""
    for key in ("OPENMIMICRY_CONFIG_PATH", "OPENMIMICRY_PROFILE"):
        monkeypatch.delenv(key, raising=False)
    return load_config(FIXTURES / "configs" / "integration.yaml", env={})


@pytest.fixture
async def wiring(integration_config: AppConfig) -> AsyncIterator[Wiring]:
    """Yield a fully-wired :class:`Wiring`. Cleans up at teardown."""
    bridge = BroadcastBridge()
    w = await build_runtime(integration_config, ws_bridge=bridge)
    await w.speech.start()
    await w.orchestrator.start()
    try:
        yield w
    finally:
        # Mirror main.py's graceful shutdown budget.
        try:
            await asyncio.wait_for(_teardown(w), timeout=2.0)
        except asyncio.TimeoutError:
            pass


async def _teardown(w: Wiring) -> None:
    await asyncio.gather(
        w.orchestrator.stop(),
        w.speech.stop(),
        return_exceptions=True,
    )
    await w.runtime.stop()


@pytest.fixture
def client_factory(integration_config: AppConfig) -> Any:
    """Return a callable that builds a TestClient with a custom lifespan.

    The default ``TestClient`` would call our lifespan which builds its
    own wiring. Tests want to drive the *same* wiring they assert on, so
    we install a per-test lifespan that injects the prepared wiring.
    """

    def _factory(w: Wiring) -> TestClient:
        app = create_app()

        @asynccontextmanager
        async def _lifespan(_app):  # type: ignore[no-redef]
            # Wire up app.state exactly as main.lifespan does.
            async def _handle_user_text(text: str) -> None:
                await run_chat_turn(
                    text,
                    bus=w.bus,
                    llm=w.llm,
                    tasks=w.tasks,
                    speech=w.speech,
                    intent_fn=w.intent,
                )

            async def _apply_mode_toggle(key: str, value: bool) -> None:
                if key == "live_wake":
                    if value:
                        await w.speech.enable_live_listening(wake_names=None)
                    else:
                        await w.speech.disable_live_listening()
                elif key == "agent_voice" and not value:
                    await w.speech.interrupt()

            _app.state.wiring = w
            _app.state.bridge = w.bridge or BroadcastBridge()
            _app.state.handle_user_text = _handle_user_text
            _app.state.apply_mode_toggle = _apply_mode_toggle
            yield

        app.router.lifespan_context = _lifespan
        return TestClient(app)

    return _factory


@pytest.fixture
def client(client_factory: Any, wiring: Wiring) -> Iterator[TestClient]:
    """The most common fixture: a TestClient bound to the live wiring."""
    with client_factory(wiring) as c:
        yield c


# ---------------------------------------------------------------------------
# Convenience accessors onto the underlying mocks.
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_llm(wiring: Wiring) -> Any:
    return wiring.llm


@pytest.fixture
def mock_stt(wiring: Wiring) -> Any:
    return wiring.stt


@pytest.fixture
def mock_tts(wiring: Wiring) -> Any:
    return wiring.tts


@pytest.fixture
def mock_tasks(wiring: Wiring) -> Any:
    """The first registered task adapter (the mock)."""
    by_family = wiring.adapters_by_family.get("tasks", {})
    if not by_family:
        return None
    return next(iter(by_family.values()))
