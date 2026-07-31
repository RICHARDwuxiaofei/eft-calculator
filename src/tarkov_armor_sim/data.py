from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from pathlib import Path

from .models import Ammo, ArmorLayer, ArmorLayerType, ArmorMaterial

DATA_VERSION = "eft-1.0.6.0-snapshot-2026-07-30"

SEED_AMMO = (
    Ammo("m855a1", "5.56x45mm M855A1", "M855A1", "5.56x45", 47, 40, 52, 1, 945, aliases=("855a1", "绿头")),
    Ammo("m855", "5.56x45mm M855", "M855", "5.56x45", 53, 31, 37, 1, 922, aliases=("855",)),
    Ammo("m995", "5.56x45mm M995", "M995", "5.56x45", 42, 53, 58, 1, 1013, aliases=("995",)),
    Ammo("762bp", "7.62x39mm BP gzh", "BP", "7.62x39", 58, 47, 63, 1, 730, aliases=("7n23", "БП")),
    Ammo("7n40", "5.45x39mm 7N40", "7N40", "5.45x39", 52, 42, 50, 1, 915, aliases=("7н40",)),
    Ammo("545bp", "5.45x39mm BP gs", "BP", "5.45x39", 48, 45, 48, 1, 890, aliases=("БП",)),
    Ammo("m80", "7.62x51mm M80", "M80", "7.62x51", 80, 41, 66, 1, 833, aliases=("308",)),
    Ammo("ap20", "12/70 AP-20 armor-piercing slug", "AP-20", "12/70", 164, 37, 65, 1, 510, aliases=("ap20", "独头弹")),
    Ammo("buckshot", "12/70 8.5mm Magnum buckshot", "Magnum", "12/70", 50, 2, 26, 8, 385, aliases=("鹿弹", "magnum buck")),
)


def default_armor_presets() -> dict[str, tuple[ArmorLayer, ...]]:
    return {
        "5级陶瓷插板 + 3级软甲": (
            ArmorLayer("ceramic5", "5级陶瓷插板", ArmorLayerType.PLATE, 5, 45, 45, 45, ArmorMaterial.CERAMIC, 0.80, 0.10, True),
            ArmorLayer("aramid3", "3级芳纶内衬", ArmorLayerType.SOFT, 3, 40, 40, 40, ArmorMaterial.ARAMID, 0.30, 0.18, False),
        ),
        "满耐久6级钢板": (
            ArmorLayer("steel6", "6级钢板", ArmorLayerType.PLATE, 6, 60, 60, 60, ArmorMaterial.STEEL, 0.35, 0.08, True),
        ),
        "仅3级软甲": (
            ArmorLayer("soft3", "3级软甲", ArmorLayerType.SOFT, 3, 50, 50, 50, ArmorMaterial.ARAMID, 0.30, 0.20, False),
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
        for ammo in SEED_AMMO:
            payload = asdict(ammo)
            payload["aliases"] = list(ammo.aliases)
            search = " ".join(
                (ammo.name, ammo.short_name, ammo.caliber, *ammo.aliases)
            ).casefold()
            self.connection.execute(
                "INSERT OR REPLACE INTO ammo(id,payload,search_text) VALUES(?,?,?)",
                (ammo.id, json.dumps(payload, ensure_ascii=False), search),
            )
        self.connection.execute(
            "INSERT OR REPLACE INTO metadata(key,value) VALUES('data_version',?)",
            (DATA_VERSION,),
        )
        self.connection.commit()

    def all_ammo(self) -> list[Ammo]:
        rows = self.connection.execute("SELECT payload FROM ammo ORDER BY id").fetchall()
        return [Ammo(**json.loads(row["payload"])) for row in rows]

    def apply_ammo_snapshot(self, snapshot: dict) -> None:
        """Atomically replace normalized ammo while preserving user tables."""
        records = snapshot.get("ammo", [])
        if not records:
            raise ValueError("快照不包含弹药")
        with self.connection:
            self.connection.execute("DELETE FROM ammo")
            for raw in records:
                payload = {key: value for key, value in raw.items() if key != "provenance"}
                payload["aliases"] = list(payload.get("aliases", []))
                search = " ".join(
                    (
                        payload["name"],
                        payload["short_name"],
                        payload["caliber"],
                        *payload["aliases"],
                    )
                ).casefold()
                self.connection.execute(
                    "INSERT INTO ammo(id,payload,search_text) VALUES(?,?,?)",
                    (
                        payload["id"],
                        json.dumps(payload, ensure_ascii=False),
                        search,
                    ),
                )
            self.connection.execute(
                "INSERT OR REPLACE INTO metadata(key,value) VALUES('data_version',?)",
                (snapshot["snapshot_id"],),
            )
            self.connection.execute(
                "INSERT OR REPLACE INTO metadata(key,value) VALUES('last_sync_at',?)",
                (snapshot["created_at"],),
            )

    def search_ammo(self, query: str, caliber: str = "") -> list[Ammo]:
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
        result = []
        for ammo in self.all_ammo():
            haystack = " ".join(
                (ammo.name, ammo.short_name, ammo.caliber, *ammo.aliases)
            ).casefold()
            normalized_haystack = normalize(haystack)
            matches = all(token in normalized_haystack for token in tokens)
            if collapsed_query:
                matches = matches and collapsed_query in normalized_haystack
            if matches and (
                not caliber or ammo.caliber == caliber
            ):
                result.append(ammo)
        result.sort(
            key=lambda ammo: (
                0 if ammo.id in favorite_ids else 1,
                recent_ids.get(ammo.id, 10_000),
                ammo.caliber,
                ammo.short_name.casefold(),
            )
        )
        return result

    def set_favorite(self, ammo_id: str, favorite: bool) -> None:
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
        return bool(
            self.connection.execute(
                "SELECT 1 FROM favorites WHERE kind='ammo' AND item_id=?", (ammo_id,)
            ).fetchone()
        )

    def mark_recent(self, ammo_id: str) -> None:
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
