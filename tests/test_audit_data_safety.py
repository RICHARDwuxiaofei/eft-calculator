import asyncio
import json
from copy import deepcopy
from dataclasses import asdict, replace

import pytest
from test_sync import FakeAdapter

from tarkov_armor_sim.data import SEED_AMMO, Database
from tarkov_armor_sim.sync import DataSynchronizer, SnapshotStore


def snapshot(record, date="2026-10-25T00:00:00+00:00"):
    return {"snapshot_id":"audit", "created_at":date, "ammo":[asdict(record)]}


def test_older_snapshot_does_not_rollback_newer_database(tmp_path):
    db = Database(tmp_path/"data.sqlite3")
    original = db.all_ammo()[0]
    newer = replace(original, damage=123, source_version="tarkov.dev-2026-10-25")
    db.apply_ammo_snapshot(snapshot(newer))
    before = db.all_ammo()
    with pytest.raises(ValueError, match="older"):
        db.apply_ammo_snapshot(snapshot(original, "2026-10-01T00:00:00+00:00"))
    assert db.all_ammo() == before
    db.connection.close()


def test_online_merge_preserves_manual_overrides(tmp_path):
    db = Database(tmp_path/"data.sqlite3")
    original = db.all_ammo()[0]
    db.apply_ammo_snapshot(snapshot(replace(original, damage=123, source_version="manual-override")))
    db.apply_ammo_snapshot(snapshot(replace(original, damage=22, source_version="tarkov.dev-2026-10-25")))
    assert next(x for x in db.all_ammo() if x.id == original.id).damage == 123
    db.connection.close()


def test_hash_tampering_is_rejected_before_database_mutation(tmp_path):
    db = Database(tmp_path/"data.sqlite3")
    before = db.all_ammo()
    payload = snapshot(SEED_AMMO[0])
    payload["sha256"] = "0"*64
    with pytest.raises(ValueError, match="SHA-256"):
        db.apply_ammo_snapshot(payload)
    assert db.all_ammo() == before
    db.connection.close()


def test_corrupt_cache_uses_valid_backup_without_destroying_bytes(tmp_path):
    store = SnapshotStore(tmp_path)
    asyncio.run(DataSynchronizer(store,(FakeAdapter(),)).sync(force=True))
    valid = store.current_path.read_bytes()
    store.backup_path.write_bytes(valid)
    store.current_path.write_text("{broken", encoding="utf-8")
    assert store.read()["ammo"]
    assert store.current_path.read_text() == "{broken"
    newer = deepcopy(json.loads(valid))
    newer["created_at"] = "2026-10-25T00:00:00+00:00"
    store.atomic_write(newer)
    assert store.backup_path.read_bytes() == valid


def test_older_cache_never_replaces_current(tmp_path):
    store = SnapshotStore(tmp_path)
    asyncio.run(DataSynchronizer(store,(FakeAdapter(),)).sync(force=True))
    newer = store.read()
    newer["created_at"] = "2026-10-25T00:00:00+00:00"
    store.atomic_write(newer)
    before = store.current_path.read_bytes()
    older = deepcopy(newer)
    older["created_at"] = "2026-09-25T00:00:00+00:00"
    with pytest.raises(ValueError, match="older"):
        store.atomic_write(older)
    assert store.current_path.read_bytes() == before


def test_search_accepts_reordered_tokens(tmp_path):
    db = Database(tmp_path/"search.sqlite3")
    assert any(x.short_name == "M855A1" for x in db.search_ammo("M855A1 5.56"))
    db.connection.close()
