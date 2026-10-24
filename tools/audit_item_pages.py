"""Resolve individual Wiki infoboxes by their embedded EFT node ID, not fuzzy names."""
from __future__ import annotations

import concurrent.futures
import hashlib
import json
import re
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/"artifacts/audit-2026-10-25"


def fetch_batch(batch):
    index, items = batch
    params = {"action":"query", "titles":"|".join(items), "prop":"revisions",
              "rvprop":"content|timestamp|ids", "rvslots":"main", "formatversion":"2",
              "format":"json", "redirects":"1"}
    reply = httpx.get("https://escapefromtarkov.fandom.com/api.php", params=params,
                      timeout=30, follow_redirects=True)
    reply.raise_for_status()
    (OUT/f"sources/wiki-items-{index:02d}.json").write_bytes(reply.content)
    return {"file":f"wiki-items-{index:02d}.json", "url":str(reply.url),
            "sha256":hashlib.sha256(reply.content).hexdigest(), "data":reply.json()}


def main():
    catalog = json.loads((ROOT/"src/tarkov_armor_sim/resources/items/catalog.json").read_text(encoding="utf-8"))
    items = catalog["ammo"]+catalog["armor"]
    titles = ["9x21mm 7N42 Zubilo" if x["id"]=="6576f4708ca9c4381d16cd9d" else x["name"].replace("Global Armor's", "Global Armor’s") for x in items]
    batches = [(i//20,titles[i:i+20]) for i in range(0,len(titles),20)]
    OUT.mkdir(parents=True, exist_ok=True)
    sources, errors, pages = [], [], {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(fetch_batch,batch) for batch in batches]
        for i, future in enumerate(futures):
            try:
                source = future.result()
                for page in source.pop("data").get("query",{}).get("pages",[]):
                    if "missing" in page:
                        continue
                    rev = page["revisions"][0]
                    content = rev["slots"]["main"]["content"]
                    node = re.search(r"^\|\s*node\s*=\s*([a-f0-9]{24})",content,re.MULTILINE)
                    if not node:
                        continue
                    fields = dict(re.findall(r"^\|\s*([^=\n]+?)\s*=([^\n]*)",content,re.MULTILINE))
                    pages[node.group(1)] = {"title":page["title"], "pageid":page["pageid"],
                                           "revision":rev["revid"], "timestamp":rev["timestamp"],
                                           "fields":{k.strip():v.strip() for k,v in fields.items()}}
                sources.append(source)
                print("Wiki batch",i,"resolved",len(pages),flush=True)
            except (httpx.HTTPError,KeyError,ValueError) as exc:
                errors.append({"batch":i,"error":str(exc)})
    observations = []
    for item in items:
        page = pages.get(item["id"])
        if page is None:
            observations.append({"id":item["id"],"name":item["name"],"status":"unresolved"})
            continue
        numeric = {"damage":"damage", "penetration":"penetration_power", "armor damage":"armor_damage_percent", "velocity":"muzzle_velocity"} if item in catalog["ammo"] else {"durability":"durability", "armor class":"armor_class"}
        for wiki_field, field in numeric.items():
            raw = page["fields"].get(wiki_field, "")
            match = re.fullmatch(r"([0-9.]+)(?:\s*m/s)?",raw)
            value = float(match.group(1)) if match else None
            observations.append({"id":item["id"],"name":item["name"],"field":field,"old_value":item.get(field),
                                 "observed_value":value,"raw_value":raw,"status":"unparsed" if value is None else "match" if value==item.get(field) else "conflict",
                                 "url":"https://escapefromtarkov.fandom.com/wiki/"+page["title"].replace(" ","_"),
                                 "wiki_revision":page["revision"],"wiki_timestamp":page["timestamp"],
                                 "retrieved_date":"2026-10-25", "confidence":"exact-embedded-item-id"})
    report = {"sources":sources,"pages_by_item_id":pages,"observations":observations,"errors":errors,
              "counts":{"requested":len(items),"exact_ids_resolved":len(pages),"conflicts":sum(x["status"]=="conflict" for x in observations)}}
    (OUT/"item-pages.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report["counts"]))
    print("Unresolved:",[x["name"] for x in observations if x["status"]=="unresolved"])
    print("Conflicts:",[x for x in observations if x["status"]=="conflict"])


if __name__ == "__main__":
    main()
