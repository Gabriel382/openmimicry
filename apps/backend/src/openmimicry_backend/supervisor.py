"""Authoritative backend lifecycle, component health, and turn admission.

The supervisor is deliberately small: it does not run LLM or voice work.  It
owns the process identity and the *lease* that permits exactly one submitted
turn to use the conversation pipeline.  Every visible state change is emitted
from that lease, so a late completion from an older subsystem cannot release a
newer turn.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from openmimicry.core import (
    ComponentHealthChanged,
    EventBus,
    RuntimeStateChanged,
    TurnStateChanged,
)

__all__ = ["RuntimeSupervisor", "TurnAdmission", "TurnSource"]


TurnSource = Literal["text", "push_to_talk", "continuous", "wake", "task"]
RuntimeState = Literal["starting", "ready", "refreshing", "stopping", "stopped", "degraded"]


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class TurnAdmission:
    """Result of an atomic turn-admission attempt."""

    accepted: bool
    turn_id: str
    sequence: int
    source: TurnSource
    reason: str | None = None
    active_turn_id: str | None = None


@dataclass(frozen=True, slots=True)
class _ActiveTurn:
    turn_id: str
    sequence: int
    source: TurnSource


class RuntimeSupervisor:
    """Own runtime readiness and a strict, non-queueing turn lease."""

    def __init__(
        self,
        *,
        bus: EventBus,
        initial_state: RuntimeState = "starting",
        instance_id: str | None = None,
    ) -> None:
        self._bus = bus
        self.instance_id = instance_id or str(uuid4())
        self._state: RuntimeState = initial_state
        self._reason: str | None = None
        self._active: _ActiveTurn | None = None
        self._sequence = 0
        self._lock = asyncio.Lock()
        self._components: dict[str, dict[str, Any]] = {}

    @property
    def state(self) -> RuntimeState:
        return self._state

    @property
    def active_turn_id(self) -> str | None:
        return self._active.turn_id if self._active else None

    @property
    def can_accept_turn(self) -> bool:
        return self._state == "ready" and self._active is None

    def snapshot(self) -> dict[str, Any]:
        active = self._active
        return {
            "instance_id": self.instance_id,
            "state": self._state,
            "ready": self.can_accept_turn,
            "reason": self._reason,
            "active_turn_id": active.turn_id if active else None,
            "active_turn_sequence": active.sequence if active else None,
            "active_turn_source": active.source if active else None,
        }

    def components_snapshot(self) -> dict[str, dict[str, Any]]:
        return {key: dict(value) for key, value in self._components.items()}

    async def set_runtime_state(self, state: RuntimeState, *, reason: str | None = None) -> None:
        async with self._lock:
            self._state = state
            self._reason = reason
            event = RuntimeStateChanged(
                ts=_now(),
                instance_id=self.instance_id,
                state=state,
                ready=state == "ready" and self._active is None,
                reason=reason,
            )
        self._bus.publish(event)

    async def try_begin_turn(self, *, source: TurnSource) -> TurnAdmission:
        """Acquire the conversation lease or return a visible rejection.

        There is intentionally no wait path.  Callers must retry after the
        active turn reaches a terminal state.
        """

        async with self._lock:
            self._sequence += 1
            turn_id = str(uuid4())
            sequence = self._sequence
            active = self._active
            if self._state != "ready":
                admission = TurnAdmission(
                    accepted=False,
                    turn_id=turn_id,
                    sequence=sequence,
                    source=source,
                    reason=f"runtime_{self._state}",
                    active_turn_id=active.turn_id if active else None,
                )
            elif active is not None:
                admission = TurnAdmission(
                    accepted=False,
                    turn_id=turn_id,
                    sequence=sequence,
                    source=source,
                    reason="turn_in_progress",
                    active_turn_id=active.turn_id,
                )
            else:
                self._active = _ActiveTurn(turn_id=turn_id, sequence=sequence, source=source)
                admission = TurnAdmission(
                    accepted=True,
                    turn_id=turn_id,
                    sequence=sequence,
                    source=source,
                )

        if not admission.accepted:
            self._publish_turn(admission, "rejected", admission.reason)
            return admission

        self._publish_turn(admission, "accepted")
        self._publish_turn(admission, "thinking")
        return admission

    async def complete_turn(self, admission: TurnAdmission) -> bool:
        return await self._finish_turn(admission, "completed")

    async def fail_turn(self, admission: TurnAdmission, *, reason: str) -> bool:
        return await self._finish_turn(admission, "failed", reason=reason)

    async def cancel_turn(self, admission: TurnAdmission, *, reason: str = "cancelled") -> bool:
        return await self._finish_turn(admission, "cancelled", reason=reason)

    async def _finish_turn(
        self,
        admission: TurnAdmission,
        state: Literal["completed", "failed", "cancelled"],
        *,
        reason: str | None = None,
    ) -> bool:
        async with self._lock:
            active = self._active
            if active is None or active.turn_id != admission.turn_id:
                return False
            self._active = None
        self._publish_turn(admission, state, reason)
        return True

    def update_component(
        self,
        *,
        family: str,
        adapter: str,
        healthy: bool,
        required: bool,
        actual_device: str | None = None,
        last_error: str | None = None,
    ) -> dict[str, Any]:
        component = f"{family}:{adapter}"
        state = "healthy" if healthy else ("unavailable" if required else "degraded")
        snapshot = {
            "instance_id": self.instance_id,
            "component": component,
            "family": family,
            "adapter": adapter,
            "state": state,
            "required": required,
            "actual_device": actual_device,
            "last_error": last_error,
        }
        previous = self._components.get(component)
        self._components[component] = snapshot
        if snapshot != previous:
            self._bus.publish(ComponentHealthChanged(ts=_now(), **snapshot))
        return dict(snapshot)

    def _publish_turn(
        self,
        admission: TurnAdmission,
        state: Literal[
            "accepted", "thinking", "presenting", "completed", "failed", "cancelled", "rejected"
        ],
        reason: str | None = None,
    ) -> None:
        self._bus.publish(
            TurnStateChanged(
                ts=_now(),
                turn_id=admission.turn_id,
                sequence=admission.sequence,
                state=state,
                source=admission.source,
                reason=reason,
                active_turn_id=admission.active_turn_id,
            )
        )
