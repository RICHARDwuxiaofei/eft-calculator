import json
import sqlite3
from dataclasses import asdict, replace

from tarkov_armor_sim.data import SEED_AMMO, Database
from tarkov_armor_sim.legacy_db import repair_legacy_ammo_payloads


def _write_legacy_ammo(path, *, muzzle_velocity=0, ballistic_coefficient=None):
    payload = asdict(
        replace(
            SEED_AMMO[0],
            id="manual-legacy-round",
            source_version="manual-override",
        )
    )
    # Simulate persisted data written by an older release. Mutate the serialized
    # payload directly so current Ammo validation does not reject the fixture
    # before it reaches the database migration path we are testing.
    payload["muzzle_velocity"] = muzzle_velocity
    payload["ballistic_coefficient"] = ballistic_coefficient

    connection = sqlite3.connect(path)
    try:
        connection.execute(
            "CREATE TABLE ammo (id TEXT PRIMARY KEY, payload TEXT NOT NULL, search_text TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO ammo(id,payload,search_text) VALUES(?,?,?)",
            (payload["id"], json.dumps(payload), "legacy test"),
        )
        connection.commit()
    finally:
        connection.close()
    return payload


def test_repairs_zero_muzzle_velocity_without_overwriting_user_record(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    original = _write_legacy_ammo(path, muzzle_velocity=0)

    assert repair_legacy_ammo_payloads(path) == 1

    connection = sqlite3.connect(path)
    try:
        repaired = json.loads(
            connection.execute(
                "SELECT payload FROM ammo WHERE id='manual-legacy-round'"
            ).fetchone()[0]
        )
    finally:
        connection.close()

    assert repaired["muzzle_velocity"] is None
    assert repaired["damage"] == original["damage"]
    assert repaired["penetration_power"] == original["penetration_power"]
    assert repaired["source_version"] == "manual-override"

    database = Database(path)
    try:
        restored = next(ammo for ammo in database.all_ammo() if ammo.id == "manual-legacy-round")
        assert restored.muzzle_velocity is None
        assert restored.damage == original["damage"]
    finally:
        database.connection.close()


def test_repairs_all_invalid_optional_positive_ballistics(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    _write_legacy_ammo(path, muzzle_velocity=-1, ballistic_coefficient=float("nan"))

    assert repair_legacy_ammo_payloads(path) == 1

    connection = sqlite3.connect(path)
    try:
        repaired = json.loads(connection.execute("SELECT payload FROM ammo").fetchone()[0])
    finally:
        connection.close()

    assert repaired["muzzle_velocity"] is None
    assert repaired["ballistic_coefficient"] is None


def test_valid_legacy_ballistics_are_left_untouched(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    _write_legacy_ammo(path, muzzle_velocity=945, ballistic_coefficient=0.25)

    assert repair_legacy_ammo_payloads(path) == 0

    connection = sqlite3.connect(path)
    try:
        payload = json.loads(connection.execute("SELECT payload FROM ammo").fetchone()[0])
    finally:
        connection.close()

    assert payload["muzzle_velocity"] == 945
    assert payload["ballistic_coefficient"] == 0.25
