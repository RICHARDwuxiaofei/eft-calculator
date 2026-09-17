from __future__ import annotations

import argparse
import json
import sqlite3
from dataclasses import asdict, replace
from pathlib import Path

from tarkov_armor_sim.data import SEED_AMMO


def create_legacy_database(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()

    payload = asdict(
        replace(
            SEED_AMMO[0],
            id="legacy-smoke-round",
            source_version="manual-override",
        )
    )
    # Reproduce legacy persisted data without constructing an invalid current Ammo.
    payload["muzzle_velocity"] = 0
    payload["ballistic_coefficient"] = 0

    connection = sqlite3.connect(path)
    try:
        connection.execute(
            "CREATE TABLE ammo (id TEXT PRIMARY KEY, payload TEXT NOT NULL, search_text TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO ammo(id,payload,search_text) VALUES(?,?,?)",
            (payload["id"], json.dumps(payload), "legacy smoke"),
        )
        connection.commit()
    finally:
        connection.close()


def assert_repaired(path: Path) -> None:
    connection = sqlite3.connect(path)
    try:
        row = connection.execute(
            "SELECT payload FROM ammo WHERE id='legacy-smoke-round'"
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        raise SystemExit("legacy smoke row disappeared during startup")
    payload = json.loads(row[0])
    if payload.get("muzzle_velocity") is not None:
        raise SystemExit("muzzle_velocity was not repaired to null")
    if payload.get("ballistic_coefficient") is not None:
        raise SystemExit("ballistic_coefficient was not repaired to null")
    if payload.get("source_version") != "manual-override":
        raise SystemExit("legacy user record was unexpectedly replaced")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=("create", "assert-repaired"))
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    if args.operation == "create":
        create_legacy_database(args.path)
    else:
        assert_repaired(args.path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
