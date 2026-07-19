from __future__ import annotations

import asyncio
import json
import sqlite3
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

from openmimicry.memory import (
    HindsightMemory,
    LocalSQLiteMemory,
    MemoryCandidate,
    MemoryService,
    NullMemory,
)
from openmimicry.memory.extractors import DeterministicExtractor


def test_deterministic_extractor_only_uses_explicit_first_person_facts() -> None:
    extractor = DeterministicExtractor()
    records = extractor.extract(
        "My name is Henri. I prefer dark themes. Alice lives in Paris.",
        "Thanks!",
    )
    assert [(record.predicate, record.value) for record in records] == [
        ("name", "Henri"),
        ("preference", "dark themes"),
    ]


async def test_local_sqlite_deduplicates_recalls_edits_and_deletes(tmp_path: Path) -> None:
    provider = LocalSQLiteMemory(tmp_path / "memory.sqlite3")
    candidate = MemoryCandidate(predicate="preference", value="Dark themes")
    await provider.retain([candidate, candidate], source="test")

    records = await provider.list()
    assert len(records) == 1
    assert (await provider.recall("Which theme do I prefer?", limit=5))[0].value == "Dark themes"

    changed = MemoryCandidate(predicate="preference", value="Light themes")
    assert await provider.update(records[0].id, changed) is True
    assert (await provider.list())[0].value == "Light themes"
    assert await provider.delete(records[0].id) is True
    assert await provider.list() == []


async def test_memory_service_observe_is_non_blocking_and_never_accepts_audio() -> None:
    class SlowProvider(NullMemory):
        def __init__(self) -> None:
            self.saved = asyncio.Event()

        async def retain(self, candidates, *, source: str) -> None:
            await asyncio.sleep(0.02)
            assert candidates[0].predicate == "name"
            self.saved.set()

    provider = SlowProvider()
    service = MemoryService(provider=provider)
    service.observe("My name is Henri.", "Nice to meet you.", source="test")
    assert not provider.saved.is_set()
    await asyncio.wait_for(provider.saved.wait(), timeout=0.2)
    await service.close()


async def test_memory_context_respects_deadline() -> None:
    class HangingProvider(NullMemory):
        async def recall(self, query: str, *, limit: int):
            await asyncio.sleep(1)
            return []

    service = MemoryService(provider=HangingProvider(), retrieval_deadline_ms=10)
    assert await service.context("anything") is None


async def test_local_sqlite_enforces_retention_on_read(tmp_path: Path) -> None:
    database = tmp_path / "memory.sqlite3"
    provider = LocalSQLiteMemory(database, retention_days=30)
    await provider.retain(
        [MemoryCandidate(predicate="preference", value="Dark themes")], source="test"
    )
    expired = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()
    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE memories SET updated_at = ?", (expired,))
    assert await provider.list() == []


async def test_hindsight_adapter_accepts_result_objects_and_preserves_source(
    monkeypatch,
) -> None:
    class FakeClient:
        def __init__(self, *, base_url: str) -> None:
            self.base_url = base_url
            self.retained: list[dict[str, object]] = []

        def retain(self, **values) -> None:
            self.retained.append(values)

        def recall(self, **_values):
            return types.SimpleNamespace(
                results=[
                    types.SimpleNamespace(
                        memory_id="remote-1",
                        content=json.dumps(
                            {
                                "subject": "user",
                                "predicate": "preference",
                                "value": "dark themes",
                                "confidence": 0.9,
                                "source": "conversation:test",
                            }
                        ),
                    ),
                    {"id": "remote-2", "text": "The user prefers concise replies."},
                ]
            )

    module = types.ModuleType("hindsight_client")
    module.Hindsight = FakeClient
    monkeypatch.setitem(sys.modules, "hindsight_client", module)

    provider = HindsightMemory(base_url="http://127.0.0.1:8888")
    await provider.retain(
        [MemoryCandidate(predicate="like", value="octopuses")], source="test-source"
    )
    records = await provider.recall("preferences", limit=2)

    assert provider._client.retained[0]["bank_id"] == "openmimicry"
    assert json.loads(provider._client.retained[0]["content"])["source"] == "test-source"
    assert [record.id for record in records] == ["remote-1", "remote-2"]
    assert records[0].source == "conversation:test"
    assert records[1].predicate == "memory"
