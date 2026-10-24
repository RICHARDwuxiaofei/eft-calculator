"""Verify all shipped bytes against the same exact-ID source; never replace an item."""
from __future__ import annotations

import concurrent.futures
import hashlib
import io
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ITEMS = ROOT/"src/tarkov_armor_sim/resources/items"
OUT = ROOT/"artifacts/audit-2026-10-25"


def verify(pair):
    item_id, entry = pair
    row = {"id": item_id, "url": entry["url"], "old_sha256": entry["sha256"],
           "retrieved_at": datetime.now(UTC).isoformat()}
    try:
        reply = httpx.get(entry["url"], timeout=15, follow_redirects=True)
        reply.raise_for_status()
        with Image.open(io.BytesIO(reply.content)) as image:
            image.load()
        row.update(sha256=hashlib.sha256(reply.content).hexdigest(), status=reply.status_code)
        row["match"] = row["sha256"] == entry["sha256"]
        if not row["match"]:
            target = OUT/"changed-images"
            target.mkdir(parents=True, exist_ok=True)
            (target/f"{item_id}.webp").write_bytes(reply.content)
    except (httpx.HTTPError, OSError, ValueError) as exc:
        row["error"] = str(exc)
    return row


def main():
    manifest = json.loads((ITEMS/"image-manifest.json").read_text(encoding="utf-8"))
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        rows = list(pool.map(verify, manifest["items"].items()))
    OUT.mkdir(parents=True, exist_ok=True)
    result = {"counts": {"total": len(rows), "unchanged": sum(r.get("match", False) for r in rows),
                         "changed": sum(r.get("match") is False for r in rows),
                         "errors": sum("error" in r for r in rows)}, "items": rows}
    (OUT/"online-images.json").write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(result["counts"]))


if __name__ == "__main__":
    main()
