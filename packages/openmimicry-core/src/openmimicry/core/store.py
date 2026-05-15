"""``RuntimeStore`` — an immutable, snapshot-shaped view of "what's true now".

The store reflects the most recent observable state of the runtime: the last
``AvatarDirective``, the most recent user / assistant text, whether TTS is
currently playing, whether live-wake is on, and the active task table.

Every mutation produces a **new** ``RuntimeStore`` instance (Pydantic
``model_copy`` under the hood) — the previous snapshot is never modified.
This makes the store cheap to share across coroutines and easy to test:
hold the "before" snapshot and assert against the "after" snapshot.

The store is *not* the bus. Modules publish events; ``Runtime`` consumes
them, folds them into a new snapshot, and replaces the live reference.
Consumers read the live reference but never mutate.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from .schemas.avatar import AvatarDirective
from .schemas.events import (
    ConfigUpdated,
    LLMReplyComplete,
    RuntimeEvent,
    TaskCompleted,
    TaskSubmitted,
    TaskUpdatedEvent,
    TTSFinished,
    TTSInterrupted,
    TTSStarted,
    UserSpeechFinal,
    UserTextSubmitted,
    WakeDetected,
)
from .schemas.tasks import TaskUpdate

__all__ = ["RuntimeStore"]


class RuntimeStore(BaseModel):
    """Immutable runtime snapshot.

    Use :meth:`update` to fold a ``RuntimeEvent`` into a new snapshot. The
    original instance is unchanged.
    """

    model_config = ConfigDict(frozen=True)

    current_directive: AvatarDirective | None = None
    last_user_text: str | None = None
    last_assistant_text: str | None = None
    is_speaking: bool = False
    live_wake_enabled: bool = False
    active_tasks: dict[str, TaskUpdate] = {}

    # ---------------------------------------------------------------- update

    def update(self, event: RuntimeEvent) -> RuntimeStore:
        """Return a new store reflecting ``event``.

        Unknown / irrelevant event kinds return ``self`` unchanged so the
        caller can blindly funnel the whole bus into the store without
        special-casing.
        """
        # User text
        if isinstance(event, UserTextSubmitted):
            return self.model_copy(update={"last_user_text": event.text})
        if isinstance(event, UserSpeechFinal) and event.reason == "normal":
            return self.model_copy(update={"last_user_text": event.text})

        # Assistant text
        if isinstance(event, LLMReplyComplete):
            return self.model_copy(update={"last_assistant_text": event.full_text})

        # TTS lifecycle
        if isinstance(event, TTSStarted):
            return self.model_copy(update={"is_speaking": True})
        if isinstance(event, (TTSFinished, TTSInterrupted)):
            return self.model_copy(update={"is_speaking": False})

        # Wake
        if isinstance(event, WakeDetected):
            return self.model_copy(update={"live_wake_enabled": True})

        # Tasks — keep a small live table keyed by handle.id
        if isinstance(event, TaskSubmitted):
            # Materialise an initial "queued" TaskUpdate so consumers always
            # see a row from submit-time onward.
            initial = TaskUpdate(
                handle=event.handle,
                status="queued",
                note=event.summary,
                ts=event.ts,
            )
            next_tasks = dict(self.active_tasks)
            next_tasks[event.handle.id] = initial
            return self.model_copy(update={"active_tasks": next_tasks})

        if isinstance(event, TaskUpdatedEvent):
            next_tasks = dict(self.active_tasks)
            next_tasks[event.update.handle.id] = event.update
            return self.model_copy(update={"active_tasks": next_tasks})

        if isinstance(event, TaskCompleted):
            # Promote into a final TaskUpdate so the row reflects the result.
            final = TaskUpdate(
                handle=event.handle,
                status=event.result.status,
                note=event.result.summary,
                ts=event.ts,
            )
            next_tasks = dict(self.active_tasks)
            next_tasks[event.handle.id] = final
            return self.model_copy(update={"active_tasks": next_tasks})

        # ConfigUpdated may toggle live_wake_enabled at the surface level.
        if isinstance(event, ConfigUpdated):
            diff = event.diff or {}
            live_wake = diff.get("voice", {}).get("modes", {}).get("live_wake")
            if isinstance(live_wake, bool):
                return self.model_copy(update={"live_wake_enabled": live_wake})

        return self

    # ----------------------------------------------------------- directives

    def with_directive(self, directive: AvatarDirective) -> RuntimeStore:
        """Return a new store with ``current_directive`` replaced.

        Directives are produced by the ``AvatarDirector`` (M3), not by raw
        events, so the store exposes a dedicated setter for them.
        """
        update: dict[str, object] = {"current_directive": directive}
        if directive.speaking:
            update["is_speaking"] = True
        return self.model_copy(update=update)
