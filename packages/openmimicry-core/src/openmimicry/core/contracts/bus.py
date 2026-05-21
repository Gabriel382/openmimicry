"""EventBus signature.

Source of truth: ``docs/contracts.md`` §2.2.

Unlike the rest of ``openmimicry.core.contracts``, this is **not** a
``Protocol`` — the EventBus is a concrete class owned by ``openmimicry-core``
itself. The shape lives here so consumers can type-check against it without a
runtime import cycle; the concrete implementation lives at
``openmimicry.core.bus`` and is the one every other module instantiates.

Phase 0 ships the signature only. M0 ships the working in-process,
multi-subscriber, bounded-queue implementation.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..schemas.events import RuntimeEvent

__all__ = ["EventBus"]


class EventBus:
    """In-process event bus.

    Producers call :meth:`publish` synchronously; consumers call
    :meth:`subscribe` to receive an async iterator with a private bounded queue.
    Implementations document their backpressure / drop policy.

    See ``openmimicry.core.bus`` for the concrete, M0-shipped class.
    """

    def publish(self, event: RuntimeEvent) -> None:
        """Fan out one event to every active subscriber."""
        raise NotImplementedError("provided by openmimicry.core.bus (M0)")

    def subscribe(self) -> AsyncIterator[RuntimeEvent]:
        """Open a new subscription. Closes when the bus closes."""
        raise NotImplementedError("provided by openmimicry.core.bus (M0)")

    async def aclose(self) -> None:
        """Drain and close every subscriber."""
        raise NotImplementedError("provided by openmimicry.core.bus (M0)")
