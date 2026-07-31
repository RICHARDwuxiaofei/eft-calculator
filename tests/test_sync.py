import asyncio
from dataclasses import replace

from tarkov_armor_sim.data import SEED_AMMO
from tarkov_armor_sim.data_sources.base import AdapterResult, DataSourceAdapter, SourceManifest
from tarkov_armor_sim.sync import DataSynchronizer, SnapshotStore


class FakeAdapter(DataSourceAdapter):
    name = "fake"
    priority = 1

    async def fetch(self):
        ammo = [
            replace(SEED_AMMO[index % len(SEED_AMMO)], id=f"item-{index}")
            for index in range(25)
        ]
        return AdapterResult(
            SourceManifest("fake", "https://example.invalid", "2026-07-31T00:00:00+00:00", 1, 25),
            ammo,
        )


def test_sync_validates_and_switches_atomically(tmp_path) -> None:
    store = SnapshotStore(tmp_path)
    report = asyncio.run(DataSynchronizer(store, (FakeAdapter(),)).sync(force=True))
    assert report.ok
    assert report.record_count == 25
    assert store.read()["snapshot_id"].startswith("eft-online-")


class BrokenAdapter(DataSourceAdapter):
    name = "broken"
    priority = 2

    async def fetch(self):
        raise RuntimeError("offline")


def test_failed_sync_keeps_last_good_snapshot(tmp_path) -> None:
    store = SnapshotStore(tmp_path)
    asyncio.run(DataSynchronizer(store, (FakeAdapter(),)).sync(force=True))
    before = store.current_path.read_bytes()
    report = asyncio.run(DataSynchronizer(store, (BrokenAdapter(),)).sync(force=True))
    assert not report.ok
    assert store.current_path.read_bytes() == before


class ConflictingAdapter(FakeAdapter):
    name = "conflicting"
    priority = 0

    async def fetch(self):
        result = await super().fetch()
        result.manifest = SourceManifest(
            "conflicting",
            "https://example.invalid/low",
            "2026-07-31T00:00:01+00:00",
            0,
            25,
        )
        result.ammo[0] = replace(result.ammo[0], damage=result.ammo[0].damage + 10)
        return result


def test_conflicts_keep_higher_priority_and_are_recorded(tmp_path) -> None:
    store = SnapshotStore(tmp_path)
    report = asyncio.run(
        DataSynchronizer(store, (FakeAdapter(), ConflictingAdapter())).sync(force=True)
    )
    snapshot = store.read()
    assert report.ok
    assert report.conflicts == 1
    assert snapshot["conflicts"][0]["field"] == "damage"
    assert next(item for item in snapshot["ammo"] if item["id"] == "item-0")["damage"] == 47
