"""Build a deterministic, audited catalog from archived Wiki + author-chart facts.

Usage: python tools/build_verified_catalog.py --source-dir /path/to/archive
No fetched JavaScript is executed. No ballistic number comes from the old tracker
snapshot: it is used only as an item-ID/name alias dictionary.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path
from urllib.parse import unquote

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
VERSION = "wiki-reviewed-2026-09-16"
WIKI_URL = "https://www.eftarkov.com/news/web_33.html"
CHART_URL = "https://eft-ammo.vercel.app/"
NAME_OVERRIDES = {
    "6576f4708ca9c4381d16cd9d": "9x21mm 7N42",
    "66a0d1e0ed648d72fe064d06": ".50 AE Copper Solid",
    "660137d8481cc6907a0c5cda": "20/70 TSS Armor Piercing Slug",
    "660137ef76c1b56143052be8": "20/70 Dangerous Game Slug",
    "64b8ee384b75259c590fa89b": "12/70 Piranha",
    "6601380580e77cfd080e3418": "20/70 flechette",
    "62330bfadc5883093563729b": ".357 Magnum HP",
    "5c3df7d588a4501f290594e5": "9x19mm Green Tracer",
    "6196365d58ef8c428c287da1": ".300 Whisper",
    "62330c40bdd19b369e1e53d1": ".357 Magnum SP",
}
LEGACY = {
    "m855a1": "54527ac44bdc2d36668b4567",
    "m855": "54527a984bdc2d4e668b4567",
    "m995": "59e690b686f7746c9f75e848",
    "762bp": "59e0d99486f7744a32234762",
    "7n40": "61962b617c6c7b169525f168",
    "545bp": "56dff026d2720bb8668b4567",
    "m80": "58dd3ad986f77403051cba8f",
    "ap20": "5d6e68a8a4b9360b6c0d54e2",
    "buckshot": "5d6e6806a4b936088465b17e",
}


def norm(value: str) -> str:
    return "".join(char for char in value.lower() if char.isalnum())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--armor-dir", type=Path)
    args = parser.parse_args()
    source = args.source_dir
    wiki = source / "ammo-table.txt"
    old = json.loads((source / "fallback-ammo.txt").read_text())
    chart_doc = BeautifulSoup((source / "ammo-chart.txt").read_text(), "html.parser")
    chart = json.loads(chart_doc.select_one("#__NEXT_DATA__").string)["props"]["pageProps"][
        "results"
    ]
    chart_map = {}
    for group in chart.values():
        for record in group:
            name = (
                unquote(record["wikiLink"].split("/wiki/")[-1]).replace("_", " ")
                if record.get("wikiLink")
                else record["standard"]["normalizedName"].replace("-", " ")
            )
            chart_map[norm(name)] = (name, record)
    ammo, excluded, conflicts = [], [], []
    raw_rows = BeautifulSoup(wiki.read_text(), "html.parser").select("tr")
    for tr in raw_rows:
        anchor = tr.select_one('a[href*="/news/id/"]')
        if not anchor:
            continue
        item_id = re.search(r"/id/([a-f0-9]{24})\.html", anchor["href"])[1]
        values = [cell.get_text(" ", strip=True) for cell in tr.select("td")]
        name_zh = values[0]
        name = NAME_OVERRIDES.get(
            item_id, old.get(item_id, {}).get("name", name_zh.replace("\u6beb\u7c73", "mm"))
        )
        found = chart_map.get(norm(name))
        if found is None:
            excluded.append(
                {
                    "id": item_id,
                    "name": name_zh,
                    "reason": "No current matched author-chart pellet count; explosive/flare/training entries not simulated.",
                }
            )
            continue
        name, chart_record = found
        raw_damage = chart_record["damage"]
        parts = raw_damage.split("x")
        count = int(parts[0]) if len(parts) == 2 else 1
        damage, armor_damage, pen, speed = (
            float(values[1]),
            float(values[2]),
            float(values[3]),
            float(values[5]),
        )
        for field, selected, candidate in [
            ("damage", damage, float(parts[-1])),
            ("penetration_power", pen, float(chart_record["penValue"])),
            ("muzzle_velocity", speed, float(chart_record["initialSpeed"])),
        ]:
            if selected != candidate:
                conflicts.append(
                    {
                        "id": item_id,
                        "field": field,
                        "wiki": selected,
                        "chart": candidate,
                        "resolution": "Wiki preferred; source difference retained for review",
                    }
                )
        if name.startswith(".300"):
            caliber = ".300 BLK"
        elif name.startswith(".338"):
            caliber = ".338 Lapua Magnum"
        elif name.startswith(".357"):
            caliber = ".357 Magnum"
        elif name.startswith(".366"):
            caliber = ".366 TKM"
        elif name.startswith(".308"):
            caliber = ".308 ME"
        elif name.startswith(".45"):
            caliber = ".45 ACP"
        elif name.startswith(".50"):
            caliber = ".50 BMG" if "BMG" in name else ".50 AE"
        else:
            match = re.match(r"(\d+(?:\.\d+)?[x/]\d+(?:R)?)", name)
            if not match:
                raise ValueError(f"Cannot resolve caliber: {name}")
            caliber = match[1]
        short = (
            old.get(item_id, {}).get("shortName")
            or chart_record["standard"]["translations"]["en"]["name"]
        )
        if caliber == "5.8x42":
            short = name.split()[-1]
        aliases = [key for key, canonical in LEGACY.items() if canonical == item_id]
        if item_id == LEGACY["ap20"]:
            aliases += ["ap20", "\u7a7f\u7532\u72ec\u5934", "armor-piercing"]
        item = {
            "id": item_id,
            "name": name,
            "short_name": short,
            "caliber": caliber,
            "damage": damage,
            "penetration_power": pen,
            "armor_damage_percent": armor_damage,
            "projectile_count": count,
            "muzzle_velocity": speed,
            "source_version": VERSION,
            "aliases": aliases,
            "localized_names": {"en": name, "zh": name_zh},
            "image_url": f"https://assets.tarkov.dev/{item_id}-icon.webp",
            "wiki_url": f"https://www.eftarkov.com/news/id/{item_id}.html",
        }
        ammo.append(item)
    ids = {item["id"] for item in ammo}
    if len(ids) != len(ammo) or not all(value in ids for value in LEGACY.values()):
        raise ValueError("Duplicate or unresolved legacy ammo identities")
    assert len([item for item in ammo if item["caliber"] == "5.8x42"]) == 4
    payload = {
        "schema_version": 1,
        "version": VERSION,
        "ammo": sorted(ammo, key=lambda a: a["id"]),
        "armor": [],
        "legacy_ids": LEGACY,
        "excluded": excluded,
        "conflicts": conflicts,
        "sources": [
            {
                "url": WIKI_URL,
                "file_sha256": hashlib.sha256(wiki.read_bytes()).hexdigest(),
                "fields": [
                    "damage",
                    "penetration_power",
                    "armor_damage_percent",
                    "muzzle_velocity",
                    "localized_names.zh",
                    "id",
                ],
            },
            {
                "url": CHART_URL,
                "file_sha256": hashlib.sha256((source / "ammo-chart.txt").read_bytes()).hexdigest(),
                "fields": ["projectile_count", "localized_names.en"],
                "cross_checks": ["damage", "penetration_power", "muzzle_velocity"],
            },
        ],
    }
    target = ROOT / "src/tarkov_armor_sim/resources/items/catalog.json"
    if args.armor_dir:
        add_armor_and_images(args.armor_dir, payload, target.parent)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Verified {len(ammo)} ammo; excluded {len(excluded)}; conflicts {len(conflicts)}")
    for item in conflicts:
        print(item)


def add_armor_and_images(source: Path, catalog: dict, resources: Path) -> None:
    classes = {
        "\u4e00\u7ea7": 1,
        "\u4e09\u7ea7": 3,
        "\u56db\u7ea7": 4,
        "\u4e94\u7ea7": 5,
        "\u516d\u7ea7": 6,
    }
    mats = {
        "\u805a\u4e59\u70ef": "uhmwpe",
        "\u88c5\u7532\u94a2": "steel",
        "\u590d\u5408\u6750\u6599": "combined",
        "\u94dd": "aluminum",
        "\u9676\u74f7": "ceramic",
        "\u949b": "titanium",
    }
    english = [
        "Tac-Kek SAPI Level III+ ballistic plate (Replica)",
        "PRTCTR Lightweight ballistic plate",
        "Zhuk-3 ballistic plate (Front)",
        "6B12 ballistic plates (Front)",
        "AR500 Legacy Plate ballistic plate",
        "Monoclete level III PE ballistic plate",
        "NewSphereTech level III ballistic plate",
        "SPRTN Elaphros ballistic plate",
        "SPRTN Omega ballistic plate",
        "Kiba Arms Titan ballistic plate",
        "6B13 custom ballistic plates (Back)",
        "6B23-2 ballistic plate (Back)",
        "6B33 ballistic plate (Front)",
        "Global Armor's Steel ballistic plate",
        "SAPI level III+ ballistic plate",
        "SSAPI level III+ ballistic plate (Side)",
        "TallCom Guardian ballistic plate",
        "Cult Locust ballistic plate",
        "GAC 3s15m ballistic plate",
        "Granit 4 ballistic plate (Front)",
        "Granit 4 ballistic plates (Back)",
        "Granit Br4 ballistic plate",
        "Korund-VM ballistic plates (Front)",
        "Korund-VM ballistic plate (Back)",
        "Korund-VM ballistic plate (Side)",
        "Korund-VM-K ballistic plates (Front)",
        "Korund-VM-K ballistic plate (Back)",
        "NESCO 4400-SA-MC ballistic plate",
        "ESAPI level IV ballistic plate",
        "ESBI level IV ballistic plate (Side)",
        "GAC 4sss2 ballistic plate",
        "Cult Termite ballistic plate",
        "Granit 4RS ballistic plate (Front)",
        "Granit 4RS ballistic plates (Back)",
        "Granit Br5 ballistic plate",
        "Granit ballistic plate (Side)",
        "Kiba Arms Steel ballistic plate",
        "KITECO SC-IV SA ballistic plate",
    ]
    legacy_names = {
        "tackek-replica": 0,
        "zhuk-3-front": 2,
        "6b23-2-back": 11,
        "6b33-front": 12,
        "monoclete": 5,
        "global-steel": 13,
        "elaphros": 7,
        "omega": 8,
        "titan": 9,
        "korund-front": 22,
        "korund-back": 23,
        "gac-3s15m": 18,
        "sapi-iii-plus": 14,
        "korund-side": 24,
        "kiteco": 37,
        "kiba-steel": 36,
        "esapi-iv": 28,
    }
    plates = []
    for label, block in re.findall(
        r'\{tabs-pane label="(.*?)"\}(.*?)\{/tabs-pane\}',
        (source / "web_40.html").read_text(),
        re.DOTALL,
    ):
        for li in BeautifulSoup(block, "html.parser").select("li.newMainLi"):
            a = li.select_one("a.title")
            itemid = a["href"].split("/")[-1].split(".")[0]
            meta = li.select_one(".meta").get_text(" ", strip=True)
            words = [x.strip() for x in meta.split("\u00b7")]
            i = len(plates)
            name = english[i]
            slots = []
            if "(Side)" in name:
                slots = ["left", "right"]
            elif "(Back)" in name:
                slots = ["back"]
            elif "(Front)" in name:
                slots = ["front"]
            else:
                slots = ["front", "back"]
            plates.append(
                {
                    "id": itemid,
                    "name": name,
                    "name_zh": a.get_text(),
                    "armor_class": classes[label],
                    "durability": float(re.search(r"\d+", words[0])[0]),
                    "material": mats[words[2]],
                    "slots": slots,
                    "source_version": catalog["version"],
                    "wiki_url": "https://www.eftarkov.com" + a["href"],
                    "image_url": f"https://assets.tarkov.dev/{itemid}-icon.webp",
                }
            )
    assert len(plates) == 38
    catalog["armor"] = plates
    catalog["legacy_armor_ids"] = {k: plates[v]["id"] for k, v in legacy_names.items()}
    catalog["sources"].append(
        {
            "url": "https://www.eftarkov.com/news/web_40.html",
            "file_sha256": hashlib.sha256((source / "web_40.html").read_bytes()).hexdigest(),
            "fields": ["armor.id", "armor.material", "armor.armor_class", "armor.durability"],
            "notes": "Side/back names override erroneous broad area tags. Effective durability is recomputed with primary Wiki material coefficients (ceramic 0.6), not copied from this index.",
        }
    )
    manifest = {"version": catalog["version"], "source_run": 35055738070, "items": {}}
    for kind, items in [("ammo", catalog["ammo"]), ("armor", plates)]:
        target = resources / (kind + "-live")
        target.mkdir(exist_ok=True)
        for item in items:
            f = source / (item["id"] + ".webp")
            if f.exists():
                shutil.copy2(f, target / f.name)
                manifest["items"][item["id"]] = {
                    "kind": kind,
                    "path": f"{kind}-live/{f.name}",
                    "url": item["image_url"],
                    "sha256": hashlib.sha256(f.read_bytes()).hexdigest(),
                }
            else:
                manifest["items"][item["id"]] = {
                    "kind": kind,
                    "status": "unavailable; explicit placeholder only",
                }
    (resources / "image-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
