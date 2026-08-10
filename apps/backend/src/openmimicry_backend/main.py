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
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from openmimicry.core import (
    AppConfig,
    LLMMessage,
    TaskConstraints,
    TaskHandle,
    UserSpeechFinal,
    UserTextSubmitted,
)
from openmimicry.core.config import load as load_config

from .appearance import load_appearance
from .avatar_selection import runtime_for_pack_kind
from .character_import import CharacterRegistry
from .companion_state import rehydrate_active_companion
from .conversation import ConversationCoordinator, TurnSubmission
from .diagnostics import install_diagnostics
from .local_tools import LocalToolService
from .routes import (
    admin_router,
    appearance_router,
    chat_router,
    companions_router,
    dashboard_router,
    diagnostics_router,
    health_router,
    interaction_router,
    llm_router,
    memory_router,
    mode_router,
    pack_router,
    personality_router,
    tasks_router,
    tools_router,
    voice_clone_router,
    voice_profiles_router,
)
from .routes.chat import run_chat_turn
from .supervisor import RuntimeSupervisor, TurnAdmission, TurnSource
from .user_settings import persist_avatar_selection
from .wiring import Wiring, build_runtime
from .ws import BroadcastBridge, ws_endpoint

__all__ = ["app", "create_app", "run_uvicorn"]


_log = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _module_available(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


def _load_app_config() -> tuple[AppConfig, str | None]:
    """Load :class:`AppConfig` from ``OPENMIMICRY_CONFIG_PATH`` or defaults."""
    path_env = os.environ.get("OPENMIMICRY_CONFIG_PATH")
    # v1 files are upgraded in memory only. The loader never overwrites the
    # user's source file, so rollback remains a matter of selecting the old
    # executable/config again.
    return load_config(path_env, allow_migrate=True), path_env


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Build the runtime, start the orchestrator + speech, tear it all down."""
    config, config_path = _load_app_config()
    appearance = load_appearance()
    presentation = config.interaction.response_presentation
    appearance = appearance.model_copy(
        update={
            "behaviour": appearance.behaviour.model_copy(
                update={
                    "bubble": appearance.behaviour.bubble.model_copy(
                        update={
                            "base_ms": presentation.base_ms,
                            "ms_per_character": presentation.ms_per_character,
                            "min_ms": presentation.minimum_ms,
                            "max_ms": presentation.maximum_ms,
                        }
                    )
                }
            )
        }
    )
    user_character_root = str(Path(config.app.data_dir).expanduser() / "characters")
    character_roots = [
        user_character_root,
        *(
            root
            for root in config.avatar.pack_roots
            if Path(root).expanduser().resolve() != Path(user_character_root).resolve()
        ),
    ]
    character_registry = CharacterRegistry(
        character_roots,
        reject_licenses=(
            config.distribution.reject_licenses
            if config.distribution.profile == "commercial"
            else None
        ),
    )

    # Rehydrate the last successfully activated private companion before any
    # voice or avatar adapter is constructed. The checked-in default remains
    # the first-run fallback only.
    config = rehydrate_active_companion(config, character_registry)

    # Repair stale pack/runtime combinations from earlier builds before an
    # adapter is constructed.  This makes a persisted VRM+sprite2d pairing
    # self-healing on the next launch.
    selected_pack = next(
        (item for item in character_registry.list() if item["id"] == config.avatar.pack),
        None,
    )
    if selected_pack is not None:
        required_runtime = runtime_for_pack_kind(selected_pack["kind"])
        if required_runtime is not None:
            repaired_runtime = required_runtime != config.avatar.runtime
            runtime_values = dict(config.avatar.runtimes.get(required_runtime, {}))
            runtime_values["pack_path"] = str(character_registry.resolve(config.avatar.pack))
            if required_runtime == "threejs":
                runtime_values["animation_speed"] = config.avatar.animation_speed
            runtimes = dict(config.avatar.runtimes)
            runtimes[required_runtime] = runtime_values
            config = config.model_copy(
                update={
                    "avatar": config.avatar.model_copy(
                        update={
                            "runtime": required_runtime,
                            "runtimes": runtimes,
                        }
                    )
                }
            )
            if repaired_runtime:
                persist_avatar_selection(
                    pack=config.avatar.pack,
                    runtime=required_runtime,
                )

    bridge = BroadcastBridge()
    wiring: Wiring = await build_runtime(config, ws_bridge=bridge, config_path=config_path)
    supervisor = RuntimeSupervisor(bus=wiring.bus)
    diagnostics = install_diagnostics(config.app.data_dir)
    task_journal = getattr(wiring.tasks, "journal", None)
    notifier = getattr(task_journal, "create_notification", None)
    tool_service = LocalToolService(
        config.tools,
        data_dir=config.app.data_dir,
        notify=notifier if callable(notifier) else None,
    )
    await tool_service.start()

    mode_state = {
        "continuous_listening": config.voice.modes.continuous_listening,
        "live_wake": config.voice.modes.live_wake,
        "agent_voice": config.voice.modes.agent_voice,
        "wake_names": list(wiring.speech.wake_names),
        "wake_aliases": list(getattr(wiring.speech, "wake_aliases", [])),
        "stt_model": getattr(wiring.speech, "stt_model", config.voice.stt.model),
        "post_speech_silence_duration": wiring.speech.post_speech_silence_duration,
    }
    presentation_state = {"value": config.interaction.response_presentation}
    language_state = {"value": config.interaction.language}

    def _project_aware_intent(text: str):
        request_obj = wiring.intent(text)
        if request_obj is None or request_obj.preferred_runtime != "claude_code":
            return request_obj
        journal = getattr(wiring.tasks, "journal", None)
        if journal is None:
            return request_obj
        projects = journal.list_projects()
        lowered = text.casefold()
        selected = next(
            (
                project
                for project in sorted(
                    projects, key=lambda item: len(str(item.get("name", ""))), reverse=True
                )
                if str(project.get("name") or "").casefold() in lowered
            ),
            None,
        )
        if (
            selected is None
            and len(projects) == 1
            and any(
                phrase in lowered for phrase in ("the project", "this project", "the repository")
            )
        ):
            selected = projects[0]
        if selected is None:
            return request_obj
        context = journal.project_context(str(selected["id"]))
        metadata = {
            **request_obj.metadata,
            "project_id": str(selected["id"]),
            "repository_fingerprint": str(context["current_fingerprint"]),
        }
        if isinstance(context.get("resume_session_id"), str):
            metadata["provider_session_id"] = context["resume_session_id"]
        return request_obj.model_copy(
            update={
                "constraints": TaskConstraints(working_dir=str(selected["root_path"])),
                "metadata": metadata,
            }
        )

    async def _run_ordered_turn(text: str, history) -> str | None:
        memory_context = await wiring.memory.context(text)
        augmented_history = list(history)
        if memory_context:
            augmented_history.append(LLMMessage(role="system", content=memory_context))
        reply = await run_chat_turn(
            text,
            bus=wiring.bus,
            llm=wiring.llm,
            tasks=wiring.tasks,
            speech=wiring.speech if mode_state["agent_voice"] else None,
            intent_fn=_project_aware_intent,
            history=augmented_history,
            presentation=presentation_state["value"],
            voice_enabled=bool(mode_state["agent_voice"]),
            output_language=language_state["value"].output,
            tool_fn=tool_service.try_execute,
        )
        if reply:
            wiring.memory.observe(
                text,
                reply,
                source=f"conversation:{diagnostics.session_id}",
            )
        return reply

    conversation = ConversationCoordinator(
        run_turn=_run_ordered_turn,
        supervisor=supervisor,
        history_turns=config.llm.history_turns,
    )

    async def _handle_user_text(
        text: str,
        source: TurnSource = "text",
    ) -> TurnSubmission:
        async def _accepted(_admission: TurnAdmission) -> None:
            # A freshly admitted turn owns presentation.  Stop speech from the
            # previous completed turn before publishing user history.  Its late
            # TTS terminal event cannot clear this turn's authoritative
            # ``thinking`` state (the avatar director enforces that invariant).
            await wiring.speech.interrupt()
            if source == "text":
                wiring.bus.publish(UserTextSubmitted(ts=_utc_now(), text=text.strip()))

        return await conversation.submit_background(
            text,
            source=source,
            on_accepted=_accepted,
        )

    async def _apply_mode_toggle(key: str, value: bool) -> None:
        # Publish an OFF decision before awaiting microphone shutdown.  A
        # recorder may deliver one final transcript while its worker is being
        # cancelled; the speech consumer below treats that event as stale.
        if key in {"continuous_listening", "live_wake"} and not value:
            mode_state[key] = False
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
        elif stt_name == "isolated-faster-whisper":
            real_input = all(
                _module_available(module) for module in ("faster_whisper", "sounddevice", "numpy")
            )
            real_input = real_input and bool(getattr(wiring.speech, "stt_ready", False))
        if tts_name == "realtimetts":
            real_output = _module_available("RealtimeTTS")
        elif tts_name == "isolated-piper":
            tts_model = (
                Path(config.voice.tts.data_dir).expanduser() / f"{config.voice.tts.voice}.onnx"
            )
            real_output = (
                _module_available("piper")
                and tts_model.is_file()
                and Path(f"{tts_model}.json").is_file()
            )
            real_output = real_output and bool(getattr(wiring.speech, "tts_ready", False))
        elif tts_name == "elevenlabs":
            real_output = bool(getattr(wiring.tts, "has_credentials", False))
        return {
            **mode_state,
            "listening_mode": getattr(wiring.speech, "listening_mode", "off"),
            "ptt_active": getattr(wiring.speech, "ptt_active", False),
            "wake_names": list(getattr(wiring.speech, "wake_names", ["Mimi"])),
            "wake_aliases": list(getattr(wiring.speech, "wake_aliases", [])),
            "stt_model": str(getattr(wiring.speech, "stt_model", "medium.en")),
            "stt_runtime": dict(getattr(wiring.stt, "runtime_info", {})),
            "post_speech_silence_duration": float(
                getattr(wiring.speech, "post_speech_silence_duration", 1.0)
            ),
            "stt_adapter": stt_name,
            "tts_adapter": tts_name,
            "real_input": real_input,
            "real_output": real_output,
            "llm_backend": getattr(wiring.llm, "active_backend", None),
            "llm_model": getattr(
                wiring.llm,
                "active_model",
                getattr(getattr(wiring.llm, "_settings", None), "model", "unknown"),
            ),
            "history_turns": conversation.memory.max_turns,
            "diagnostics_session": diagnostics.session_id,
            "diagnostics_log": str(diagnostics.log_path),
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
    app.state.config = config
    app.state.presentation_state = presentation_state
    app.state.language_state = language_state
    app.state.bridge = bridge
    app.state.handle_user_text = _handle_user_text
    app.state.apply_mode_toggle = _apply_mode_toggle
    app.state.mode_state = mode_state
    app.state.appearance = appearance
    app.state.get_mode_status = _mode_status
    app.state.cancel_task = _cancel_task
    app.state.conversation = conversation
    app.state.supervisor = supervisor
    app.state.character_registry = character_registry
    app.state.active_pack = config.avatar.pack
    app.state.active_voice_profile = config.voice.active_profile
    app.state.memory = wiring.memory
    app.state.diagnostics = diagnostics
    app.state.tool_service = tool_service

    speech_subscription = wiring.bus.subscribe()

    async def _consume_speech_turns() -> None:
        async for event in speech_subscription:
            if not isinstance(event, UserSpeechFinal):
                continue
            spoken = event.text.strip()
            if not event.accepted or not spoken or event.reason == "interrupted":
                continue
            if event.input_mode == "wake" and not mode_state["live_wake"]:
                _log.info("Ignoring stale wake transcript after wake listening was disabled")
                continue
            if event.input_mode == "continuous" and not mode_state["continuous_listening"]:
                _log.info("Ignoring stale continuous transcript after listening was disabled")
                continue
            await _handle_user_text(spoken, source=event.input_mode)

    speech_turn_task = asyncio.create_task(
        _consume_speech_turns(), name="openmimicry.backend.speech_turns"
    )

    await wiring.speech.start()
    if mode_state["continuous_listening"]:
        await wiring.speech.enable_continuous_listening()
    elif mode_state["live_wake"]:
        await wiring.speech.enable_live_listening(wake_names=None)
    await wiring.orchestrator.start()
    await supervisor.set_runtime_state("ready")
    await bridge.remember({"type": "runtime.state", **supervisor.snapshot()})

    _mount_static_characters(app, config)

    try:
        yield
    finally:
        await supervisor.set_runtime_state("stopping", reason="application_shutdown")
        speech_turn_task.cancel()
        with suppress(asyncio.CancelledError, Exception):
            await speech_turn_task
        language_task = language_state.get("task")
        if isinstance(language_task, asyncio.Task) and not language_task.done():
            language_task.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await language_task
        await conversation.close()
        await tool_service.close()
        try:
            await asyncio.wait_for(_graceful_shutdown(wiring), timeout=2.0)
        except TimeoutError:
            _log.warning("backend lifespan: graceful shutdown exceeded 2s budget")
        finally:
            await supervisor.set_runtime_state("stopped", reason="application_shutdown")
            diagnostics.close()


async def _graceful_shutdown(wiring: Wiring) -> None:
    await asyncio.gather(
        wiring.orchestrator.stop(),
        wiring.speech.stop(),
        wiring.memory.close(),
        _close_tasks(wiring.tasks),
        return_exceptions=True,
    )
    await wiring.runtime.stop()


async def _close_tasks(tasks: object) -> None:
    closer = getattr(tasks, "close", None)
    if callable(closer):
        await cast(Callable[[], Awaitable[Any]], closer)()


def create_app() -> FastAPI:
    app = FastAPI(
        title="OpenMimicry Backend",
        version="1.9.2",
        lifespan=lifespan,
    )

    app.include_router(health_router)
    app.include_router(chat_router)
    app.include_router(companions_router)
    app.include_router(dashboard_router)
    app.include_router(diagnostics_router)
    app.include_router(mode_router)
    app.include_router(llm_router)
    app.include_router(interaction_router)
    app.include_router(memory_router)
    app.include_router(personality_router)
    app.include_router(tasks_router)
    app.include_router(tools_router)
    app.include_router(voice_clone_router)
    app.include_router(voice_profiles_router)
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
