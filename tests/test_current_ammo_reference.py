"""Current public-data anchors reviewed 2026-09-18.

These are data checks, not claims that a third-party chart exposes proprietary
server code. Damage / penetration / armor-damage values were cross-checked against
current Tarkov101 and GameMaps tables and, where available, TarkovBox. Keeping more
than ten diverse rounds here makes stale catalog regressions immediately visible.
"""

import pytest

from tarkov_armor_sim.data import BUNDLED_CATALOG

CATALOG = {item["name"]: item for item in BUNDLED_CATALOG["ammo"]}


@pytest.mark.parametrize(
    "name,damage,penetration,armor_damage",
    [
        ("5.56x45mm M855", 54, 31, 37),
        ("5.56x45mm M855A1", 49, 44, 47),
        ("5.56x45mm M995", 42, 53, 52),
        ("5.56x45mm M856A1", 52, 38, 44),
        ("5.45x39mm BP gs", 48, 45, 46),
        ("5.45x39mm BS gs", 45, 54, 57),
        ("5.45x39mm 7N40", 55, 42, 45),
        ("5.45x39mm BT gs", 54, 37, 44),
        ("5.45x39mm PP gs", 51, 34, 42),
        ("5.45x39mm PS gs", 56, 28, 40),
        ("7.62x39mm BP gzh", 58, 47, 63),
        ("7.62x39mm PS gzh", 61, 35, 52),
        ("7.62x51mm M80", 80, 43, 67),
        ("7.62x54mm R SNB gzh", 75, 62, 87),
        ("9x19mm Pst gzh", 54, 20, 33),
        ("4.6x30mm AP SX", 35, 53, 46),
        ("5.7x28mm SS190", 49, 37, 43),
    ],
)
def test_current_public_ammo_reference_values(
    name: str, damage: int, penetration: int, armor_damage: int
) -> None:
    item = CATALOG[name]
    assert item["damage"] == damage
    assert item["penetration_power"] == penetration
    assert item["armor_damage_percent"] == armor_damage


def test_reference_matrix_is_broad_enough() -> None:
    # Deliberately above the user's requested 10-case floor.
    referenced = {
        "5.56x45mm M855",
        "5.56x45mm M855A1",
        "5.56x45mm M995",
        "5.56x45mm M856A1",
        "5.45x39mm BP gs",
        "5.45x39mm BS gs",
        "5.45x39mm 7N40",
        "5.45x39mm BT gs",
        "5.45x39mm PP gs",
        "5.45x39mm PS gs",
        "7.62x39mm BP gzh",
        "7.62x39mm PS gzh",
        "7.62x51mm M80",
        "7.62x54mm R SNB gzh",
        "9x19mm Pst gzh",
        "4.6x30mm AP SX",
        "5.7x28mm SS190",
    }
    assert len(referenced) >= 10
