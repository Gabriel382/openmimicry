"""openmimicry-backend: FastAPI process + WebSocket projection.

Only ``openmimicry_backend.wiring`` imports concrete adapter classes; every
other module here uses Protocols from :mod:`openmimicry.core.contracts`.

See ``docs/modules/M6_backend.md`` for the brief.
"""

from __future__ import annotations

__version__ = "0.2.0a0"
__all__ = ["__version__"]
