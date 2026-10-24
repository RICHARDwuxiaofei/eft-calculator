"""Archive public evidence without executing remote content or overwriting the catalog."""
from __future__ import annotations

import concurrent.futures
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "artifacts" / "audit-2026-10-25" / "sources"
SOURCES = {
    "wiki-ballistics": "https://escapefromtarkov.fandom.com/wiki/Ballistics",
    "wiki-plates": "https://escapefromtarkov.fandom.com/wiki/Armor_plates",
    "wiki-changelog": "https://escapefromtarkov.fandom.com/wiki/Changelog",
    "wiki-cn-ammo": "https://www.eftarkov.com/news/web_33.html",
    "wiki-cn-plates": "https://www.eftarkov.com/news/web_40.html",
    "nofood-chart": "https://eft-ammo.vercel.app/",
    "official-news": "https://www.escapefromtarkov.com/news",
    "tarkov-dev-api": "https://api.tarkov.dev/graphql",
    "wiki-api-plates": "https://escapefromtarkov.fandom.com/api.php?action=parse&page=Armor_plates&prop=wikitext&format=json",
    "wiki-api-ballistics": "https://escapefromtarkov.fandom.com/api.php?action=parse&page=Ballistics&prop=wikitext&format=json",
    "wiki-api-changelog": "https://escapefromtarkov.fandom.com/api.php?action=parse&page=Changelog&prop=wikitext&format=json",
    "wiki-ammo-whisper": "https://escapefromtarkov.fandom.com/api.php?action=parse&page=.300_Whisper&prop=wikitext&format=json",
    "wiki-ammo-spbt": "https://escapefromtarkov.fandom.com/api.php?action=parse&page=7.62x54mm_R_SP_BT&prop=wikitext&format=json",
    "wiki-ammo-7n42": "https://escapefromtarkov.fandom.com/api.php?action=parse&page=9x21mm_7N42_Zubilo&prop=wikitext&format=json",
}
QUERY = """{ en: ammo(lang: en) { item { id name shortName iconLink wikiLink }
caliber damage penetrationPower armorDamage projectileCount initialSpeed
fragmentationChance ricochetChance } zh: ammo(lang: zh) { item { id name shortName } }
items(type: armor, lang: en) { id name shortName iconLink wikiLink properties {
... on ItemPropertiesArmor { class durability material { name destructibility } } } } }"""


def fetch(entry):
    key, url = entry
    record = {"url": url, "retrieved_at": datetime.now(UTC).isoformat()}
    try:
        with httpx.Client(timeout=25, follow_redirects=True, headers={
            "User-Agent": "EFT-Calculator/2.2.2 public-data-audit"
        }) as client:
            reply = (client.post(url, json={"query": QUERY}) if key == "tarkov-dev-api"
                     else client.get(url))
        body = reply.content
        filename = key + (".json" if key == "tarkov-dev-api" else ".html")
        (TARGET / filename).write_bytes(body)
        record.update(status=reply.status_code, sha256=hashlib.sha256(body).hexdigest(),
                      bytes=len(body), file=filename, final_url=str(reply.url))
        if reply.status_code >= 400:
            record["error"] = reply.text[:300]
    except (httpx.HTTPError, OSError) as exc:
        record["error"] = str(exc)
    print(key, record.get("status"), record.get("bytes"), record.get("error", ""), flush=True)
    return key, record


def main():
    TARGET.mkdir(parents=True, exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        results = dict(pool.map(fetch, SOURCES.items()))
    (TARGET / "manifest.json").write_text(json.dumps({
        "audit_date": "2026-10-25", "sources": results,
        "game_version": "not-yet-confirmed", "catalog_modified": False,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
