"""Optional long-term memory with deterministic and LLM extractors."""

from .models import MemoryCandidate, MemoryRecord
from .providers import HindsightMemory, LocalSQLiteMemory, MemoryProvider, NullMemory
from .service import MemoryService

__all__ = [
    "HindsightMemory",
    "LocalSQLiteMemory",
    "MemoryCandidate",
    "MemoryProvider",
    "MemoryRecord",
    "MemoryService",
    "NullMemory",
]

__version__ = "1.6.4"
