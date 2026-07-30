import json

from tarkov_armor_sim.data import SEED_AMMO, Database, default_armor_presets
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


def test_exports(tmp_path) -> None:
    scenario = ShotScenario(
        SEED_AMMO[0], default_armor_presets()["5级陶瓷插板 + 3级软甲"]
    )
    result = analyze(scenario, CurrentApproximation())
    json_path = tmp_path / "result.json"
    csv_path = tmp_path / "result.csv"
    export_json(json_path, scenario, result)
    export_csv(csv_path, scenario, result)
    assert json.loads(json_path.read_text(encoding="utf-8"))["ruleset_version"]
    assert "M855A1" in csv_path.read_text(encoding="utf-8-sig")
