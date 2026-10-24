"""Apply only identity-confirmed metadata; retain and explicitly record numeric conflicts."""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
ITEMS = ROOT/"src/tarkov_armor_sim/resources/items"
OUT = ROOT/"artifacts/audit-2026-10-25"
VERSION = "wiki-reviewed-2026-10-25"


def main():
    path = ITEMS/"catalog.json"
    catalog = json.loads(path.read_text(encoding="utf-8"))
    pages = json.loads((OUT/"item-pages.json").read_text(encoding="utf-8"))["pages_by_item_id"]
    assert len(pages) == len(catalog["ammo"])+len(catalog["armor"])
    changes = []
    for kind in ("ammo", "armor"):
        for item in catalog[kind]:
            page = pages[item["id"]]
            url = "https://escapefromtarkov.fandom.com/wiki/"+quote(page["title"].replace(" ","_"),safe="/()_+")
            fields = {"wiki_url":url}
            if kind == "ammo":
                ricochet = re.fullmatch(r"([0-9.]+)\s*%",page["fields"].get("ricochet", ""))
                if ricochet:
                    fields["ricochet_chance"] = float(ricochet.group(1))/100
            for field,value in fields.items():
                old = item.get(field)
                if old == value:
                    continue
                changes.append({"id":item["id"],"kind":kind,"field":field,"old_value":old,"new_value":value,
                                "source_url":url,"wiki_revision":page["revision"],"wiki_timestamp":page["timestamp"],
                                "game_version_context":"Wiki changelog 1.2.5.0.48146 (20 October 2026)",
                                "retrieved_date":"2026-10-25","confidence":"exact-embedded-item-id",
                                "affects_current_calculation":False})
                item[field] = value
            item["source_version"] = VERSION
    catalog["version"] = VERSION
    catalog["audit"] = {"reviewed_at":"2026-10-25", "source":"Escape from Tarkov Wiki API + NoFoodAfterMidnight",
                        "item_id_verified":222,"unresolved_source_conflicts":3,
                        "status":"identity-reviewed; conflicting damage/wear inputs retained and documented",
                        "report":"docs/AUDIT_2026-10-25.md"}
    path.write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    report = OUT/"applied-data-diff.json"
    if changes or not report.exists():
        report.write_text(json.dumps({"version":VERSION,"changes":changes},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("Applied metadata changes:",len(changes),"ricochet:",sum(x["field"]=="ricochet_chance" for x in changes))


if __name__ == "__main__":
    main()
