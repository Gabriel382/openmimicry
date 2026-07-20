"""Null, local SQLite, and optional Hindsight provider adapters."""

from __future__ import annotations

import asyncio
import json
import re
import sqlite3
from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

from .models import MemoryCandidate, MemoryRecord

__all__ = ["HindsightMemory", "LocalSQLiteMemory", "MemoryProvider", "NullMemory"]


class MemoryProvider(Protocol):
    async def recall(self, query: str, *, limit: int) -> list[MemoryRecord]: ...
    async def retain(self, candidates: Sequence[MemoryCandidate], *, source: str) -> None: ...
    async def list(self, *, limit: int = 100) -> list[MemoryRecord]: ...
    async def update(self, memory_id: str, candidate: MemoryCandidate) -> bool: ...
    async def delete(self, memory_id: str) -> bool: ...
    async def clear(self) -> int: ...
    async def close(self) -> None: ...


class NullMemory:
    async def recall(self, query: str, *, limit: int) -> list[MemoryRecord]:
        return []

    async def retain(self, candidates: Sequence[MemoryCandidate], *, source: str) -> None:
        return None

    async def list(self, *, limit: int = 100) -> list[MemoryRecord]:
        return []

    async def delete(self, memory_id: str) -> bool:
        return False

    async def update(self, memory_id: str, candidate: MemoryCandidate) -> bool:
        return False

    async def clear(self) -> int:
        return 0

    async def close(self) -> None:
        return None


class LocalSQLiteMemory:
    """Small local store with exact-fact dedupe and lexical retrieval."""

    def __init__(self, path: str | Path, *, retention_days: int | None = 365) -> None:
        self._path = Path(path).expanduser()
        self._retention_days = retention_days
        self._lock = asyncio.Lock()
        self._initialized = False

    async def _ensure_ready(self) -> None:
        if self._initialized:
            return
        async with self._lock:
            if not self._initialized:
                await asyncio.to_thread(self._initialize_sync)
                self._initialized = True

    def _connect(self) -> sqlite3.Connection:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self._path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _initialize_sync(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                subject TEXT NOT NULL,
                predicate TEXT NOT NULL,
                value TEXT NOT NULL,
                normalized_value TEXT NOT NULL,
                confidence REAL NOT NULL,
                source TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(subject, predicate, normalized_value)
                )"""
            )

    async def retain(self, candidates: Sequence[MemoryCandidate], *, source: str) -> None:
        if not candidates:
            return
        await self._ensure_ready()
        async with self._lock:
            await asyncio.to_thread(self._retain_sync, list(candidates), source[:256])

    def _retain_sync(self, candidates: list[MemoryCandidate], source: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            self._purge_expired_sync(connection)
            for candidate in candidates:
                normalized = " ".join(candidate.value.casefold().split())
                connection.execute(
                    """INSERT INTO memories
                    (id, subject, predicate, value, normalized_value, confidence, source, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(subject, predicate, normalized_value) DO UPDATE SET
                    confidence = MAX(confidence, excluded.confidence),
                    source = excluded.source,
                    updated_at = excluded.updated_at""",
                    (
                        uuid4().hex,
                        candidate.subject,
                        candidate.predicate,
                        candidate.value,
                        normalized,
                        candidate.confidence,
                        source,
                        now,
                        now,
                    ),
                )

    async def recall(self, query: str, *, limit: int) -> list[MemoryRecord]:
        await self._ensure_ready()
        rows = await asyncio.to_thread(self._all_rows_sync, 1000)
        tokens = set(re.findall(r"[\w'-]+", query.casefold()))

        def score(row: sqlite3.Row) -> tuple[int, str]:
            haystack = f"{row['predicate']} {row['value']}".casefold()
            overlap = sum(token in haystack for token in tokens)
            return overlap, row["updated_at"]

        ranked = sorted(rows, key=score, reverse=True)
        positive = [row for row in ranked if score(row)[0] > 0]
        selected = positive[: max(0, limit)]
        return [_row_to_record(row) for row in selected]

    async def list(self, *, limit: int = 100) -> list[MemoryRecord]:
        await self._ensure_ready()
        rows = await asyncio.to_thread(self._all_rows_sync, max(0, min(limit, 1000)))
        return [_row_to_record(row) for row in rows]

    def _all_rows_sync(self, limit: int) -> list[sqlite3.Row]:
        with self._connect() as connection:
            self._purge_expired_sync(connection)
            return list(
                connection.execute(
                    "SELECT * FROM memories ORDER BY updated_at DESC LIMIT ?", (limit,)
                ).fetchall()
            )

    async def delete(self, memory_id: str) -> bool:
        await self._ensure_ready()
        async with self._lock:
            return await asyncio.to_thread(self._delete_sync, memory_id)

    async def update(self, memory_id: str, candidate: MemoryCandidate) -> bool:
        await self._ensure_ready()
        async with self._lock:
            return await asyncio.to_thread(self._update_sync, memory_id, candidate)

    def _update_sync(self, memory_id: str, candidate: MemoryCandidate) -> bool:
        normalized = " ".join(candidate.value.casefold().split())
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            self._purge_expired_sync(connection)
            try:
                cursor = connection.execute(
                    """UPDATE memories SET subject = ?, predicate = ?, value = ?,
                    normalized_value = ?, confidence = ?, updated_at = ? WHERE id = ?""",
                    (
                        candidate.subject,
                        candidate.predicate,
                        candidate.value,
                        normalized,
                        candidate.confidence,
                        now,
                        memory_id,
                    ),
                )
            except sqlite3.IntegrityError:
                return False
            return cursor.rowcount > 0

    def _delete_sync(self, memory_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            return cursor.rowcount > 0

    async def clear(self) -> int:
        await self._ensure_ready()
        async with self._lock:
            return await asyncio.to_thread(self._clear_sync)

    def _clear_sync(self) -> int:
        with self._connect() as connection:
            count = int(connection.execute("SELECT COUNT(*) FROM memories").fetchone()[0])
            connection.execute("DELETE FROM memories")
            return count

    def _purge_expired_sync(self, connection: sqlite3.Connection) -> int:
        if self._retention_days is None:
            return 0
        cutoff = (datetime.now(timezone.utc) - timedelta(days=self._retention_days)).isoformat()
        cursor = connection.execute("DELETE FROM memories WHERE updated_at < ?", (cutoff,))
        return cursor.rowcount

    async def close(self) -> None:
        return None


class HindsightMemory:
    """Thin optional wrapper around the official Hindsight Python client."""

    def __init__(self, *, base_url: str, bank_id: str = "openmimicry") -> None:
        try:
            from hindsight_client import Hindsight  # pyright: ignore[reportMissingImports]
        except ImportError as exc:
            raise RuntimeError(
                "Hindsight is not installed. Install openmimicry-memory[hindsight]."
            ) from exc
        self._client: Any = Hindsight(base_url=base_url)
        self._bank_id = bank_id

    async def retain(self, candidates: Sequence[MemoryCandidate], *, source: str) -> None:
        for candidate in candidates:
            content = json.dumps({**candidate.model_dump(), "source": source})
            await asyncio.to_thread(
                self._client.retain,
                bank_id=self._bank_id,
                content=content,
            )

    async def recall(self, query: str, *, limit: int) -> list[MemoryRecord]:
        raw = await asyncio.to_thread(
            self._client.recall,
            bank_id=self._bank_id,
            query=query,
        )
        items = getattr(raw, "results", raw if isinstance(raw, list) else [])
        records: list[MemoryRecord] = []
        for item in list(items)[:limit]:
            if isinstance(item, dict):
                content = item.get("content") or item.get("text") or item.get("memory")
                item_id = item.get("id") or item.get("memory_id")
            else:
                content = (
                    getattr(item, "content", None)
                    or getattr(item, "text", None)
                    or getattr(item, "memory", None)
                )
                item_id = getattr(item, "id", None) or getattr(item, "memory_id", None)
            if not isinstance(content, str):
                continue
            try:
                payload = json.loads(content)
                source = str(payload.pop("source", "hindsight"))
                candidate = MemoryCandidate.model_validate(payload)
            except Exception:
                source = "hindsight"
                candidate = MemoryCandidate(
                    predicate="memory",
                    value=content[:2048],
                    confidence=1.0,
                )
            records.append(
                MemoryRecord(
                    id=str(item_id or uuid4().hex),
                    source=source[:256],
                    **candidate.model_dump(),
                )
            )
        return records

    async def list(self, *, limit: int = 100) -> list[MemoryRecord]:
        return await self.recall("user preferences facts", limit=limit)

    async def delete(self, memory_id: str) -> bool:
        raise NotImplementedError("Hindsight record deletion is managed by its service API")

    async def update(self, memory_id: str, candidate: MemoryCandidate) -> bool:
        raise NotImplementedError("Hindsight record editing is managed by its service API")

    async def clear(self) -> int:
        raise NotImplementedError("Hindsight bank deletion is managed by its service API")

    async def close(self) -> None:
        return None


def _row_to_record(row: sqlite3.Row) -> MemoryRecord:
    return MemoryRecord(
        id=row["id"],
        subject=row["subject"],
        predicate=row["predicate"],
        value=row["value"],
        confidence=float(row["confidence"]),
        source=row["source"],
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )
