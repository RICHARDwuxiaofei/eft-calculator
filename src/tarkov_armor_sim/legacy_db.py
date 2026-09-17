from __future__ import annotations

import json
import sqlite3
from math import isfinite
from pathlib import Path

_OPTIONAL_POSITIVE_BALLISTICS = ("muzzle_velocity", "ballistic_coefficient")


def _is_valid_optional_positive(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and isfinite(value)
        and value > 0
    )


def repair_legacy_ammo_payloads(path: Path) -> int:
    """Repair optional ballistics written by older releases before strict validation.

    Older databases may contain ``0`` (or another invalid value) for optional
    ballistics such as muzzle velocity. The current :class:`Ammo` model treats
    unknown values as ``None`` and correctly rejects non-positive values. Repair
    only those nullable metadata fields instead of inventing a physical value or
    replacing the rest of the user's stored record.

    Returns the number of ammo rows that were repaired.
    """
    if not path.exists():
        return 0

    connection = sqlite3.connect(path)
    try:
        has_ammo_table = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='ammo'"
        ).fetchone()
        if has_ammo_table is None:
            return 0

        repairs: list[tuple[str, str]] = []
        for item_id, payload in connection.execute("SELECT id, payload FROM ammo").fetchall():
            try:
                raw = json.loads(payload)
            except (TypeError, ValueError):
                # Do not guess how to reconstruct an unrelated corrupt payload.
                # Database validation will still surface that corruption clearly.
                continue
            if not isinstance(raw, dict):
                continue

            changed = False
            for field in _OPTIONAL_POSITIVE_BALLISTICS:
                if field not in raw or raw[field] is None:
                    continue
                if not _is_valid_optional_positive(raw[field]):
                    raw[field] = None
                    changed = True

            if changed:
                repairs.append(
                    (
                        json.dumps(raw, ensure_ascii=False, allow_nan=False),
                        item_id,
                    )
                )

        if repairs:
            with connection:
                connection.executemany(
                    "UPDATE ammo SET payload=? WHERE id=?",
                    repairs,
                )
        return len(repairs)
    finally:
        connection.close()
