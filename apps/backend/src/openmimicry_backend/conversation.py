"""Bounded successful-turn memory and a single ordered submission lane."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections import deque
from collections.abc import Awaitable, Callable, Sequence

from openmimicry.core import LLMMessage

__all__ = ["ConversationCoordinator", "ConversationMemory"]


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


class ConversationCoordinator:
    """Serialize accepted turns so replies cannot overtake one another."""

    def __init__(self, *, run_turn: RunTurn, history_turns: int = 4) -> None:
        self._run_turn = run_turn
        self.memory = ConversationMemory(max_turns=history_turns)
        self._lock = asyncio.Lock()
        self._tasks: set[asyncio.Task[str | None]] = set()
        self._sequence = 0

    async def submit(self, text: str) -> str | None:
        clean = text.strip()
        if not clean:
            return None
        self._sequence += 1
        sequence = self._sequence
        queued_at = time.monotonic()
        _log.info("Turn %04d queued: chars=%d", sequence, len(clean))
        async with self._lock:
            started_at = time.monotonic()
            _log.info(
                "Turn %04d started: queue_wait=%.2fs history_turns=%d",
                sequence,
                started_at - queued_at,
                len(self.memory.messages()) // 2,
            )
            try:
                reply = await self._run_turn(clean, self.memory.messages())
            except asyncio.CancelledError:
                _log.info("Turn %04d cancelled", sequence)
                raise
            except Exception:
                _log.exception("Turn %04d failed", sequence)
                raise
            if reply:
                self.memory.remember(clean, reply)
            _log.info(
                "Turn %04d completed: duration=%.2fs reply_chars=%d",
                sequence,
                time.monotonic() - started_at,
                len(reply or ""),
            )
            return reply

    def submit_background(self, text: str) -> asyncio.Task[str | None]:
        """Queue a turn without coupling UI input to LLM/TTS completion."""

        task = asyncio.create_task(self.submit(text), name="openmimicry.backend.conversation")
        self._tasks.add(task)

        def _done(completed: asyncio.Task[str | None]) -> None:
            self._tasks.discard(completed)
            if completed.cancelled():
                return
            with contextlib.suppress(Exception):
                completed.result()

        task.add_done_callback(_done)
        return task

    async def close(self) -> None:
        """Cancel queued/in-flight turns during application shutdown."""

        tasks = list(self._tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
