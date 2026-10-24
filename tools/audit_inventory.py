"""Reproducible item/field/image audit. Never substitutes identities or changes data."""
from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from urllib.parse import unquote

from bs4 import BeautifulSoup
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
ITEMS = ROOT / "src/tarkov_armor_sim/resources/items"
OUT = ROOT / "artifacts/audit-2026-10-25"


def normalized(text):
    return "".join(c for c in text.casefold() if c.isalnum())


def wiki_fields(catalog):
    """Parse only explicit Wiki cells, never guess a value from an unmatched row."""
    directory = OUT/"sources"
    body = json.loads((directory/"wiki-api-ballistics.html").read_text(encoding="utf-8"))["parse"]["wikitext"]["*"]
    plate_text = json.loads((directory/"wiki-api-plates.html").read_text(encoding="utf-8"))["parse"]["wikitext"]["*"]
    log = json.loads((directory/"wiki-api-changelog.html").read_text(encoding="utf-8"))["parse"]["wikitext"]["*"]
    version = re.search(r"^==([^=]+)==",log,re.MULTILINE).group(1)
    rows, unmatched, candidates = [], [], []
    materials = {"UHMWPE":"uhmwpe", "Armor steel":"steel", "Combined materials":"combined",
                 "Titan":"titanium", "Aluminum":"aluminum", "Aluminium":"aluminum", "Ceramic":"ceramic"}

    def cells(lines):
        return [BeautifulSoup(line.rsplit("|",1)[-1], "html.parser").get_text().strip()
                for line in lines if line.startswith("|") and not line.startswith(("|-", "|}"))]

    for kind, text, source in (("ammo",body,"https://escapefromtarkov.fandom.com/wiki/Ballistics"),
                               ("armor",plate_text,"https://escapefromtarkov.fandom.com/wiki/Armor_plates")):
        blocks = re.split(r"\n\|-", text)
        for item in catalog[kind]:
            matches = []
            for block in blocks:
                lines = block.splitlines()
                for index, line in enumerate(lines):
                    if not line.startswith(("|", "!")):
                        continue
                    names = [name.split("|",1)[0] for name in re.findall(r"\[\[([^\]]+)\]\]",line)]
                    # Wiki renamed 7N42 to 7N42 Zubilo; same caliber and cartridge designation.
                    expected_name = "9x21mm 7N42 Zubilo" if item["id"] == "6576f4708ca9c4381d16cd9d" else item["name"]
                    if normalized(expected_name) in map(normalized,names):
                        matches.append((cells(lines[index+1:]),block))
                        break
            if len(matches) != 1:
                unmatched.append({"id":item["id"],"name":item["name"],"kind":kind,"matches":len(matches)})
                continue
            values, _ = matches[0]
            if kind == "armor":
                observed = {"material": materials[values[0]], "armor_class":int(values[1]),
                            "durability":float(values[3]),
                            "slots": [slot for word,slot in (("Front","front"),("Back","back"),("Sides","left"),("Sides","right")) if word in values[2]]}
            else:
                damage = re.split("[x×]",values[0])
                try:
                    observed = {"damage":float(damage[-1]), "penetration_power":float(values[1]),
                                "armor_damage_percent":float(values[2]), "muzzle_velocity":float(values[7]),
                                "projectile_count":int(damage[0]) if len(damage)==2 else 1}
                except (ValueError,IndexError):
                    unmatched.append({"id":item["id"],"name":item["name"],"kind":kind,"reason":"unparsed explicit cells","cells":values[:8]})
                    continue
            for field,value in observed.items():
                old = item.get(field)
                if isinstance(old,list):
                    equal = sorted(old)==sorted(value)
                else:
                    equal = old==value
                rows.append({"id":item["id"],"name":item["name"],"kind":kind,"field":field,
                             "old_value":old,"observed_value":value,"status":"match" if equal else "conflict",
                             "source_url":source,"game_version_context":version,"retrieved_date":"2026-10-25",
                             "confidence":"direct-community-wiki-fact","action":"none" if equal else "review"})
        known = {normalized(item["name"]) for item in catalog[kind]}
        if kind == "armor":
            for block in blocks:
                names = re.findall(r"^!\[\[([^\]]+)\]\]",block,re.MULTILINE)
                for name in names:
                    if not name.startswith("File:") and normalized(name) not in known:
                        candidates.append({"name":name,"source_url":source,"reason":"stable ID not yet confirmed; do not invent"})
    return {"wiki_version_context":version,"fields":rows,"unmatched":unmatched,"new_armor_candidates":candidates,
            "counts":{"fields":len(rows),"ammo_matched":len({r["id"] for r in rows if r["kind"]=="ammo"}),
                      "armor_matched":len({r["id"] for r in rows if r["kind"]=="armor"}),
                      "conflicts":sum(r["status"]=="conflict" for r in rows)}}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    catalog = json.loads((ITEMS / "catalog.json").read_text(encoding="utf-8"))
    manifest = json.loads((ITEMS / "image-manifest.json").read_text(encoding="utf-8"))
    source = OUT / "sources/nofood-chart.html"
    chart = json.loads(BeautifulSoup(source.read_text(encoding="utf-8"), "html.parser")
                       .select_one("#__NEXT_DATA__").string)["props"]["pageProps"]["results"]
    lookup = defaultdict(list)
    for group in chart.values():
        for row in group:
            name = unquote((row.get("wikiLink") or "").split("/wiki/")[-1]).replace("_", " ")
            if not name:
                name = row.get("standard", {}).get("normalizedName", "").replace("-", " ")
            if name:
                lookup[normalized(name)].append(row)
    fields, unmatched, matched_names = [], [], set()
    for item in catalog["ammo"]:
        candidates = lookup[normalized(item["name"])]
        if len(candidates) != 1:
            unmatched.append({"id": item["id"], "name": item["name"], "reason": "no unique exact name"})
            continue
        row = candidates[0]
        matched_names.add(normalized(item["name"]))
        damage = row["damage"].lower().split("x")
        observed = {"damage": float(damage[-1]),
                    "projectile_count": int(damage[0]) if len(damage) == 2 else 1,
                    "penetration_power": float(row["penValue"]),
                    "muzzle_velocity": float(row["initialSpeed"])}
        if row.get("fragChange"):
            observed["fragmentation_chance"] = float(row["fragChange"].rstrip("%")) / 100
        for field, value in observed.items():
            old = item.get(field)
            fields.append({"id": item["id"], "name": item["name"], "field": field,
                           "old_value": old, "observed_value": value,
                           "status": "match" if old == value else "conflict" if old is not None else "missing",
                           "source_url": "https://eft-ammo.vercel.app/",
                           "item_wiki_url": row.get("wikiLink"), "retrieved_date": "2026-10-25",
                           "game_version": "unconfirmed-by-source", "confidence": "single-maintained-community-source",
                           "action": "retain until independently corroborated" if old != value else "none"})
    images, hashes = [], defaultdict(list)
    records = catalog["ammo"] + catalog["armor"]
    for item in records:
        entry = manifest["items"].get(item["id"])
        errors = []
        result = {"id": item["id"], "name": item["name"], "manifest": entry}
        if not entry:
            errors.append("missing-manifest")
        else:
            path = ITEMS / entry["path"]
            if path.stem != item["id"] or item["id"] not in entry["url"]:
                errors.append("identity-path-mismatch")
            try:
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                if digest != entry["sha256"]:
                    errors.append("hash-mismatch")
                hashes[digest].append(item["id"])
                with Image.open(path) as image:
                    image.load()
                    extrema = image.convert("RGB").getextrema()
                    result.update(size=list(image.size), format=image.format, sha256=digest)
                    if max(high-low for low, high in extrema) < 2:
                        errors.append("blank-image")
                    if image.width < 8 or image.height < 8:
                        errors.append("tiny-image")
            except (OSError, ValueError) as exc:
                errors.append(str(exc))
        result["errors"] = errors
        images.append(result)
    duplicate_groups = [ids for ids in hashes.values() if len(ids) > 1]
    primary = wiki_fields(catalog)
    report = {"audit_date": "2026-10-25", "baseline": "2e332e3541dd1818cdc74e2710c1bce4beb7f5ca", "primary_wiki":primary,
              "counts": {"ammo": len(catalog["ammo"]), "plates": len(catalog["armor"]),
                         "exact_name_matched": len(matched_names), "checked_fields": len(fields),
                         "conflicts": sum(r["status"] == "conflict" for r in fields),
                         "missing_values": sum(r["status"] == "missing" for r in fields),
                         "images": len(images), "image_errors": sum(bool(r["errors"]) for r in images)},
              "fields": fields, "unmatched": unmatched, "images": images,
              "duplicate_hash_groups": duplicate_groups,
              "new_chart_names": [key for key in lookup if key not in matched_names],
              "coverage_limits": ["tarkov.dev armor API unavailable; Wiki armor table checked separately", "chart has no armorDamage field",
                                  "name cross-check does not prove current numeric truth", "image ID/hash is not visual proof"]}
    (OUT / "inventory.json").write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    for start in range(0, len(records), 48):
        canvas = Image.new("RGB", (1200, 8*135), "#1c2026")
        draw = ImageDraw.Draw(canvas)
        for index, item in enumerate(records[start:start+48]):
            entry = manifest["items"].get(item["id"])
            if not entry:
                continue
            x, y = (index % 6)*200, (index // 6)*135
            with Image.open(ITEMS/entry["path"]) as img:
                img = img.convert("RGBA")
                img.thumbnail((150, 95))
                canvas.paste(img, (x+(200-img.width)//2, y), img)
            draw.text((x+5,y+96), item.get("short_name", item["name"])[:26], fill="white")
            draw.text((x+5,y+114), item["id"][-12:], fill="#b0c0d0")
        canvas.save(OUT/f"image-contact-{start//48+1}.png")
    print(json.dumps(report["counts"]))
    print("PRIMARY WIKI:",json.dumps(primary["counts"]))
    print("WIKI CONFLICTS:",[(r["name"],r["field"],r["old_value"],r["observed_value"]) for r in primary["fields"] if r["status"]=="conflict"])
    print("WIKI UNMATCHED:",primary["unmatched"])
    print("NEW ARMOR CANDIDATES:",primary["new_armor_candidates"])
    print("Duplicate byte groups:", duplicate_groups)
    print("Unmatched:", [row["name"] for row in unmatched])
    print("Conflicts:", [(r["name"],r["field"],r["old_value"],r["observed_value"]) for r in fields if r["status"]=="conflict"])


if __name__ == "__main__":
    main()
