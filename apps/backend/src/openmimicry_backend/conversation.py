"""Bounded successful-turn memory and strict single-flight admission."""

from __future__ import annotations

import asyncio
import contextlib
import inspect
import logging
import time
from collections import deque
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass

from openmimicry.core import LLMMessage

from .supervisor import RuntimeSupervisor, TurnAdmission, TurnSource

__all__ = [
    "ConversationBusyError",
    "ConversationCoordinator",
    "ConversationMemory",
    "TurnSubmission",
]


_log = logging.getLogger(__name__)


class ConversationMemory:
    """Keep only complete user/assistant pairs for future LLM context."""

    def __init__(self, *, max_turns: int = 4) -> None:
        self._turns: deque[tuple[str, str]] = deque(maxlen=max(0, max_turns))

    @property
    def max_turns(self) -> int:
        return self._turns.maxlen or 0

    def messages(self) -> list[LLMMessage]:
        messages: list[LLMMessage] = []
        for user, assistant in self._turns:
            messages.append(LLMMessage(role="user", content=user))
            messages.append(LLMMessage(role="assistant", content=assistant))
        return messages

    def remember(self, user: str, assistant: str) -> None:
        if self.max_turns and user.strip() and assistant.strip():
            self._turns.append((user.strip(), assistant.strip()))


RunTurn = Callable[[str, Sequence[LLMMessage]], Awaitable[str | None]]
AcceptedHook = Callable[[TurnAdmission], Awaitable[None] | None]


@dataclass(frozen=True, slots=True)
class TurnSubmission:
    """Immediate submission result; accepted work continues in ``task``."""

    admission: TurnAdmission
    task: asyncio.Task[str | None] | None = None

    @property
    def accepted(self) -> bool:
        return self.admission.accepted

    @property
    def turn_id(self) -> str:
        return self.admission.turn_id

    @property
    def reason(self) -> str | None:
        return self.admission.reason


class ConversationBusyError(RuntimeError):
    """Raised by the blocking API when another turn owns the lease."""

    def __init__(self, admission: TurnAdmission) -> None:
        super().__init__(admission.reason or "conversation turn was rejected")
        self.admission = admission


class ConversationCoordinator:
    """Admit at most one turn; reject later attempts instead of queueing."""

    def __init__(
        self,
        *,
        run_turn: RunTurn,
        supervisor: RuntimeSupervisor,
        history_turns: int = 4,
    ) -> None:
        self._run_turn = run_turn
        self._supervisor = supervisor
        self.memory = ConversationMemory(max_turns=history_turns)
        self._tasks: set[asyncio.Task[str | None]] = set()

    async def submit(
        self,
        text: str,
        *,
        source: TurnSource = "text",
        on_accepted: AcceptedHook | None = None,
    ) -> str | None:
        submission = await self.submit_background(
            text,
            source=source,
            on_accepted=on_accepted,
        )
        if not submission.accepted or submission.task is None:
            raise ConversationBusyError(submission.admission)
        return await submission.task

    async def submit_background(
        self,
        text: str,
        *,
        source: TurnSource = "text",
        on_accepted: AcceptedHook | None = None,
    ) -> TurnSubmission:
        """Attempt admission and return without waiting for LLM completion."""

        clean = text.strip()
        if not clean:
            return TurnSubmission(
                TurnAdmission(
                    accepted=False,
                    turn_id="",
                    sequence=0,
                    source=source,
                    reason="empty",
                )
            )

        admission = await self._supervisor.try_begin_turn(source=source)
        if not admission.accepted:
            _log.info(
                "Turn %04d rejected: reason=%s active_turn=%s",
                admission.sequence,
                admission.reason,
                admission.active_turn_id,
            )
            return TurnSubmission(admission)

        task = asyncio.create_task(
            self._execute(clean, admission, on_accepted=on_accepted),
            name=f"openmimicry.backend.turn.{admission.sequence:04d}",
        )
        self._tasks.add(task)

        def _done(completed: asyncio.Task[str | None]) -> None:
            self._tasks.discard(completed)
            if completed.cancelled():
                return
            with contextlib.suppress(Exception):
                completed.result()

        task.add_done_callback(_done)
        return TurnSubmission(admission, task)

    async def _execute(
        self,
        text: str,
        admission: TurnAdmission,
        *,
        on_accepted: AcceptedHook | None,
    ) -> str | None:
        started_at = time.monotonic()
        _log.info(
            "Turn %04d started: turn_id=%s history_turns=%d",
            admission.sequence,
            admission.turn_id,
            len(self.memory.messages()) // 2,
        )
        try:
            if on_accepted is not None:
                hook_result = on_accepted(admission)
                if inspect.isawaitable(hook_result):
                    await hook_result
            reply = await self._run_turn(text, self.memory.messages())
        except asyncio.CancelledError:
            await self._supervisor.cancel_turn(admission, reason="shutdown")
            _log.info("Turn %04d cancelled", admission.sequence)
            raise
        except Exception as exc:
            await self._supervisor.fail_turn(admission, reason=f"{type(exc).__name__}: {exc}")
            _log.exception("Turn %04d failed", admission.sequence)
            raise

        if reply:
            self.memory.remember(text, reply)
        await self._supervisor.complete_turn(admission)
        _log.info(
            "Turn %04d completed: duration=%.2fs reply_chars=%d",
            admission.sequence,
            time.monotonic() - started_at,
            len(reply or ""),
        )
        return reply

    async def close(self) -> None:
        """Cancel the in-flight turn during application shutdown."""

        tasks = list(self._tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
