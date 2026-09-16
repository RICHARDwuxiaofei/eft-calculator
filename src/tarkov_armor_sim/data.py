from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from .calibers import caliber_matches
from .models import Ammo, ArmorLayer, ArmorLayerType, ArmorMaterial

DATA_VERSION = "wiki-reviewed-2026-09-16"
BUNDLED_CATALOG = json.loads((Path(__file__).parent / "resources/items/catalog.json").read_text(encoding="utf-8"))
LEGACY_AMMO_IDS = BUNDLED_CATALOG["legacy_ids"]

SEED_AMMO = (
    Ammo(
        "m855a1",
        "5.56x45mm M855A1",
        "M855A1",
        "5.56x45",
        47,
        40,
        52,
        1,
        945,
        aliases=("855a1", "绿头"),
        localized_names={"en": "5.56x45mm M855A1", "zh": "5.56x45毫米 M855A1"},
    ),
    Ammo(
        "m855",
        "5.56x45mm M855",
        "M855",
        "5.56x45",
        54,
        31,
        37,
        1,
        922,
        aliases=("855",),
        localized_names={"en": "5.56x45mm M855", "zh": "5.56x45毫米 M855"},
    ),
    Ammo(
        "m995",
        "5.56x45mm M995",
        "M995",
        "5.56x45",
        42,
        53,
        58,
        1,
        1013,
        aliases=("995",),
        localized_names={"en": "5.56x45mm M995", "zh": "5.56x45毫米 M995"},
    ),
    Ammo(
        "762bp",
        "7.62x39mm BP gzh",
        "BP",
        "7.62x39",
        58,
        47,
        63,
        1,
        730,
        aliases=("7n23", "БП", "762bp"),
        localized_names={"en": "7.62x39mm BP gzh", "zh": "7.62x39毫米 BP gzh"},
    ),
    Ammo(
        "7n40",
        "5.45x39mm 7N40",
        "7N40",
        "5.45x39",
        52,
        42,
        50,
        1,
        915,
        aliases=("7н40",),
        localized_names={"en": "5.45x39mm 7N40", "zh": "5.45x39毫米 7N40"},
    ),
    Ammo(
        "545bp",
        "5.45x39mm BP gs",
        "BP",
        "5.45x39",
        48,
        45,
        48,
        1,
        890,
        aliases=("БП", "545bp"),
        localized_names={"en": "5.45x39mm BP gs", "zh": "5.45x39毫米 BP gs"},
    ),
    Ammo(
        "m80",
        "7.62x51mm M80",
        "M80",
        "7.62x51",
        80,
        41,
        66,
        1,
        833,
        aliases=("308",),
        localized_names={"en": "7.62x51mm M80", "zh": "7.62x51毫米 M80"},
    ),
    Ammo(
        "ap20",
        "12/70 AP-20 armor-piercing slug",
        "AP-20",
        "12/70",
        164,
        37,
        65,
        1,
        510,
        aliases=("ap20", "独头弹"),
        localized_names={
            "en": "12/70 AP-20 armor-piercing slug",
            "zh": "12/70 AP-20 穿甲独头弹",
        },
    ),
    Ammo(
        "buckshot",
        "12/70 8.5mm Magnum buckshot",
        "Magnum",
        "12/70",
        50,
        2,
        26,
        8,
        385,
        aliases=("鹿弹", "magnum buck", "8.5"),
        localized_names={
            "en": "12/70 8.5mm Magnum buckshot",
            "zh": "12/70 8.5毫米“马格南”鹿弹",
        },
    ),
)

_catalog_by_id = {item["id"]: item for item in BUNDLED_CATALOG["ammo"]}
SEED_AMMO = tuple(replace(ammo,
    damage=_catalog_by_id[LEGACY_AMMO_IDS[ammo.id]]["damage"],
    penetration_power=_catalog_by_id[LEGACY_AMMO_IDS[ammo.id]]["penetration_power"],
    armor_damage_percent=_catalog_by_id[LEGACY_AMMO_IDS[ammo.id]]["armor_damage_percent"],
    muzzle_velocity=_catalog_by_id[LEGACY_AMMO_IDS[ammo.id]]["muzzle_velocity"],
    source_version=DATA_VERSION) for ammo in SEED_AMMO)


@dataclass(frozen=True)
class ArmorPlatePreset:
    id: str
    name: str
    name_zh: str
    armor_class: int
    durability: float
    material: ArmorMaterial
    slots: tuple[str, ...]

    def display_name(self, locale: str) -> str:
        return self.name_zh if locale.lower().startswith("zh") else self.name


@dataclass(frozen=True)
class ArmorCarrierPreset:
    id: str
    name: str
    name_zh: str
    defaults: dict[str, str]

    def display_name(self, locale: str) -> str:
        return self.name_zh if locale.lower().startswith("zh") else self.name


LEGACY_ARMOR_IDS = BUNDLED_CATALOG["legacy_armor_ids"]
ARMOR_PLATES = tuple(ArmorPlatePreset(item["id"], item["name"], item["name_zh"],
    item["armor_class"], item["durability"], ArmorMaterial(item["material"]),
    tuple(item["slots"])) for item in BUNDLED_CATALOG["armor"])


ARMOR_CARRIERS = (
    ArmorCarrierPreset(
        "free",
        "No carrier restriction",
        "不限载具（手动搭配）",
        {"front": "monoclete", "back": "monoclete", "left": "korund-side", "right": "korund-side"},
    ),
    ArmorCarrierPreset(
        "6b23-2",
        "6B23-2 body armor (Mountain Flora)",
        "6B23-2 防弹衣（山地迷彩）",
        {"front": "6b33-front", "back": "6b23-2-back"},
    ),
    ArmorCarrierPreset(
        "bagariy",
        "NPP KlASS Bagariy plate carrier (EMR)",
        "NPP KlASS Bagariy 防弹胸挂（EMR）",
        {
            "front": "korund-front",
            "back": "korund-back",
            "left": "korund-side",
            "right": "korund-side",
        },
    ),
    ArmorCarrierPreset(
        "slick",
        "LBT-6094A Slick Plate Carrier (Black)",
        "LBT-6094A Slick 板甲（黑色）",
        {"front": "kiba-steel", "back": "kiba-steel"},
    ),
    ArmorCarrierPreset(
        "trooper",
        "HighCom Trooper TFO body armor (MultiCam)",
        "HighCom Trooper TFO 防弹衣（MultiCam）",
        {"front": "monoclete", "back": "monoclete"},
    ),
)

ARMOR_CARRIERS = tuple(replace(carrier, defaults={slot: LEGACY_ARMOR_IDS[plate]
    for slot, plate in carrier.defaults.items()}) for carrier in ARMOR_CARRIERS)


ARMOR_SLOT_NAMES = {
    "front": {"en": "Front plate", "zh": "前插板"},
    "back": {"en": "Back plate", "zh": "后插板"},
    "left": {"en": "Left side plate", "zh": "左侧插板"},
    "right": {"en": "Right side plate", "zh": "右侧插板"},
}


def armor_plate_by_id(item_id: str) -> ArmorPlatePreset:
    return next(item for item in ARMOR_PLATES if item.id == LEGACY_ARMOR_IDS.get(item_id, item_id))


def default_armor_presets() -> dict[str, tuple[ArmorLayer, ...]]:
    return {
        "5级陶瓷插板 + 3级软甲": (
            ArmorLayer(
                "ceramic5",
                "5级陶瓷插板",
                ArmorLayerType.PLATE,
                5,
                45,
                45,
                45,
                ArmorMaterial.CERAMIC,
                0.60,
                0.10,
                True,
            ),
            ArmorLayer(
                "aramid3",
                "3级芳纶内衬",
                ArmorLayerType.SOFT,
                3,
                40,
                40,
                40,
                ArmorMaterial.ARAMID,
                0.1875,
                0.18,
                False,
            ),
        ),
        "满耐久6级钢板": (
            ArmorLayer(
                "steel6",
                "6级钢板",
                ArmorLayerType.PLATE,
                6,
                60,
                60,
                60,
                ArmorMaterial.STEEL,
                0.525,
                0.08,
                True,
            ),
        ),
        "仅3级软甲": (
            ArmorLayer(
                "soft3",
                "3级软甲",
                ArmorLayerType.SOFT,
                3,
                50,
                50,
                50,
                ArmorMaterial.ARAMID,
                0.1875,
                0.20,
                False,
            ),
        ),
        "4级钢制插板": (
            ArmorLayer(
                "global-steel4",
                "Global Armor 4级钢制插板",
                ArmorLayerType.PLATE,
                4,
                45,
                45,
                45,
                ArmorMaterial.STEEL,
                0.525,
                0.10,
                True,
            ),
        ),
        "4级聚乙烯插板": (
            ArmorLayer(
                "monoclete4",
                "Monoclete 4级聚乙烯插板",
                ArmorLayerType.PLATE,
                4,
                40,
                40,
                40,
                ArmorMaterial.UHMWPE,
                0.3375,
                0.10,
                True,
            ),
        ),
        "5级 Korund 钢板": (
            ArmorLayer(
                "korund5",
                "Korund-VM 5级钢制插板",
                ArmorLayerType.PLATE,
                5,
                60,
                60,
                60,
                ArmorMaterial.STEEL,
                0.525,
                0.09,
                True,
            ),
        ),
    }


class Database:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self._migrate()

    def _migrate(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS ammo (
              id TEXT PRIMARY KEY, payload TEXT NOT NULL, search_text TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS favorites (
              kind TEXT NOT NULL, item_id TEXT NOT NULL, PRIMARY KEY(kind, item_id)
            );
            CREATE TABLE IF NOT EXISTS recent (
              kind TEXT NOT NULL, item_id TEXT NOT NULL, used_at TEXT DEFAULT CURRENT_TIMESTAMP,
              PRIMARY KEY(kind, item_id)
            );
            CREATE TABLE IF NOT EXISTS presets (
              id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, payload TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            """
        )
        installed = self.connection.execute(
            "SELECT value FROM metadata WHERE key='bundled_catalog_version'"
        ).fetchone()
        if installed is None or installed[0] != DATA_VERSION:
            with self.connection:
                for raw in BUNDLED_CATALOG["ammo"]:
                    old = self.connection.execute("SELECT payload FROM ammo WHERE id=?", (raw["id"],)).fetchone()
                    version = json.loads(old[0]).get("source_version", "") if old else ""
                    replaceable = version.startswith(("bundled", "tarkovdata-", "TarkovTracker"))
                    if version.startswith(("tarkov.dev-", "wiki-reviewed-")):
                        replaceable = version[-10:] < "2026-09-16"
                    if old and not replaceable:
                        continue
                    self._upsert_ammo(Ammo(**raw))
                for legacy, item_id in LEGACY_AMMO_IDS.items():
                    self.connection.execute("INSERT OR IGNORE INTO favorites(kind,item_id) SELECT kind,? FROM favorites WHERE kind='ammo' AND item_id=?", (item_id, legacy))
                    self.connection.execute("INSERT OR IGNORE INTO recent(kind,item_id,used_at) SELECT kind,?,used_at FROM recent WHERE kind='ammo' AND item_id=?", (item_id, legacy))
                    self.connection.execute("DELETE FROM ammo WHERE id=?", (legacy,))
                    self.connection.execute("DELETE FROM favorites WHERE kind='ammo' AND item_id=?", (legacy,))
                    self.connection.execute("DELETE FROM recent WHERE kind='ammo' AND item_id=?", (legacy,))
                self.connection.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES('bundled_catalog_version',?)", (DATA_VERSION,))
                self.connection.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES('data_version',?)", (DATA_VERSION,))

    def _upsert_ammo(self, ammo: Ammo) -> None:
        payload = asdict(ammo)
        search = " ".join((ammo.name, ammo.short_name, ammo.caliber, *ammo.aliases,
                           *ammo.localized_names.values())).casefold()
        self.connection.execute("INSERT OR REPLACE INTO ammo(id,payload,search_text) VALUES(?,?,?)",
            (ammo.id, json.dumps(payload, ensure_ascii=False, allow_nan=False), search))

    def all_ammo(self) -> list[Ammo]:
        rows = self.connection.execute("SELECT payload FROM ammo ORDER BY id").fetchall()
        return [Ammo(**json.loads(row["payload"])) for row in rows]

    def apply_ammo_snapshot(self, snapshot: dict) -> None:
        """Validate before changing the database; never erase verified absent items."""
        records = snapshot.get("ammo", [])
        if not records:
            raise ValueError("Snapshot has no ammo")
        sources = snapshot.get("sources", [])
        if sources and all(item.get("source") == "TarkovTracker/tarkovdata" for item in sources):
            raise ValueError("Historical fallback is not allowed to replace verified data")
        if sources and snapshot.get("created_at", "")[:10] < "2026-09-16":
            raise ValueError("Cached online data predates the bundled Wiki review")
        parsed = [Ammo(**{k:v for k,v in raw.items() if k != "provenance"}) for raw in records]
        if len({a.id for a in parsed}) != len(parsed):
            raise ValueError("Duplicate ammo IDs")
        with self.connection:
            for ammo in parsed:
                self._upsert_ammo(ammo)
            self.connection.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES('data_version',?)", (snapshot["snapshot_id"],))
            self.connection.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES('last_sync_at',?)", (snapshot["created_at"],))

    def search_ammo(self, query: str, caliber: str = "", locale: str = "en_US") -> list[Ammo]:
        def normalize(value: str) -> str:
            return "".join(character for character in value.casefold() if character.isalnum())

        tokens = [normalize(token) for token in query.split() if normalize(token)]
        collapsed_query = normalize(query)
        favorite_ids = {
            row["item_id"]
            for row in self.connection.execute(
                "SELECT item_id FROM favorites WHERE kind='ammo'"
            ).fetchall()
        }
        recent_ids = {
            row["item_id"]: index
            for index, row in enumerate(
                self.connection.execute(
                    "SELECT item_id FROM recent WHERE kind='ammo' ORDER BY used_at DESC"
                ).fetchall()
            )
        }
        result: list[tuple[int, Ammo]] = []
        for ammo in self.all_ammo():
            current_name = ammo.display_name(locale)
            english_name = ammo.localized_names.get("en", ammo.name)
            values = (
                ammo.short_name,
                current_name,
                english_name,
                ammo.name,
                ammo.caliber,
                *ammo.aliases,
                *ammo.localized_names.values(),
            )
            haystack = " ".join(values).casefold()
            normalized_haystack = normalize(haystack)
            matches = all(token in normalized_haystack for token in tokens)
            if collapsed_query:
                matches = matches and collapsed_query in normalized_haystack
            if matches and caliber_matches(ammo.caliber, caliber):
                normalized_values = [normalize(value) for value in values if value]
                if not collapsed_query:
                    score = 10
                elif collapsed_query == normalize(ammo.short_name):
                    score = 0
                elif collapsed_query in [normalize(alias) for alias in ammo.aliases]:
                    score = 1
                elif any(value.startswith(collapsed_query) for value in normalized_values):
                    score = 2
                else:
                    score = 3
                result.append((score, ammo))
        result.sort(
            key=lambda scored: (
                scored[0],
                len(scored[1].short_name),
                0 if scored[1].id in favorite_ids else 1,
                recent_ids.get(scored[1].id, 10_000),
                scored[1].caliber,
                scored[1].short_name.casefold(),
            )
        )
        return [ammo for _score, ammo in result]

    def set_favorite(self, ammo_id: str, favorite: bool) -> None:
        ammo_id = LEGACY_AMMO_IDS.get(ammo_id, ammo_id)
        if favorite:
            self.connection.execute(
                "INSERT OR IGNORE INTO favorites(kind,item_id) VALUES('ammo',?)", (ammo_id,)
            )
        else:
            self.connection.execute(
                "DELETE FROM favorites WHERE kind='ammo' AND item_id=?", (ammo_id,)
            )
        self.connection.commit()

    def is_favorite(self, ammo_id: str) -> bool:
        ammo_id = LEGACY_AMMO_IDS.get(ammo_id, ammo_id)
        return bool(
            self.connection.execute(
                "SELECT 1 FROM favorites WHERE kind='ammo' AND item_id=?", (ammo_id,)
            ).fetchone()
        )

    def mark_recent(self, ammo_id: str) -> None:
        ammo_id = LEGACY_AMMO_IDS.get(ammo_id, ammo_id)
        self.connection.execute(
            "INSERT OR REPLACE INTO recent(kind,item_id,used_at) VALUES('ammo',?,CURRENT_TIMESTAMP)",
            (ammo_id,),
        )
        self.connection.commit()

    def save_preset(self, name: str, layers: tuple[ArmorLayer, ...]) -> None:
        payload = []
        for layer in layers:
            item = asdict(layer)
            item["layer_type"] = layer.layer_type.value
            item["material"] = layer.material.value
            payload.append(item)
        self.connection.execute(
            "INSERT OR REPLACE INTO presets(name,payload) VALUES(?,?)",
            (name, json.dumps(payload, ensure_ascii=False)),
        )
        self.connection.commit()


def default_database_path() -> Path:
    import os

    root = Path(os.getenv("LOCALAPPDATA", Path.home())) / "TarkovArmorSimulator"
    return root / "current.sqlite3"
