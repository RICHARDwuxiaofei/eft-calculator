import json
from dataclasses import asdict, replace

from tarkov_armor_sim.data import (
    ARMOR_CARRIERS,
    SEED_AMMO,
    Database,
    armor_plate_by_id,
    default_armor_presets,
)
from tarkov_armor_sim.engine import analyze
from tarkov_armor_sim.models import ShotScenario
from tarkov_armor_sim.rulesets import CurrentApproximation
from tarkov_armor_sim.services import export_csv, export_json


def test_search_alias_caliber_and_favorite(tmp_path) -> None:
    db = Database(tmp_path / "test.sqlite3")
    assert db.search_ammo("855a1")[0].id == "m855a1"
    assert all(a.caliber == "5.56x45" for a in db.search_ammo("", "5.56x45"))
    db.set_favorite("m855a1", True)
    assert db.is_favorite("m855a1")


def test_bilingual_partial_search_ranks_exact_short_name_first(tmp_path) -> None:
    db = Database(tmp_path / "bilingual.sqlite3")
    results = db.search_ammo("855", locale="zh_CN")
    assert results[0].id == "m855"
    assert any(item.id == "m855a1" for item in results)
    assert db.search_ammo("穿甲独头", locale="zh_CN")[0].id == "ap20"
    assert db.search_ammo("armor-piercing", locale="zh_CN")[0].id == "ap20"


def test_api_caliber_identifiers_match_human_readable_filters(tmp_path) -> None:
    db = Database(tmp_path / "api-caliber.sqlite3")
    online = replace(
        SEED_AMMO[1],
        id="54527a984bdc2d4e668b4567",
        caliber="556x45",
    )
    db.apply_ammo_snapshot(
        {
            "snapshot_id": "tracker-calibers",
            "created_at": "2026-07-31T00:00:00+00:00",
            "ammo": [asdict(online)],
        }
    )
    assert db.search_ammo("", "5.56x45")[0].id == online.id


def test_carrier_defaults_reference_real_plate_values() -> None:
    bagariy = next(item for item in ARMOR_CARRIERS if item.id == "bagariy")
    front = armor_plate_by_id(bagariy.defaults["front"])
    side = armor_plate_by_id(bagariy.defaults["left"])
    assert (front.armor_class, front.durability, front.material.value) == (
        5,
        60,
        "steel",
    )
    assert side.slots == ("left", "right")


def test_exports(tmp_path) -> None:
    scenario = ShotScenario(SEED_AMMO[0], default_armor_presets()["5级陶瓷插板 + 3级软甲"])
    result = analyze(scenario, CurrentApproximation())
    json_path = tmp_path / "result.json"
    csv_path = tmp_path / "result.csv"
    export_json(json_path, scenario, result)
    export_csv(csv_path, scenario, result)
    assert json.loads(json_path.read_text(encoding="utf-8"))["ruleset_version"]
    assert "M855A1" in csv_path.read_text(encoding="utf-8-sig")
