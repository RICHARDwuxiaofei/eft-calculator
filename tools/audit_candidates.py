"""Resolve chart-only firearm candidates before deciding whether to add them."""
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx


def main():
    titles = ["7.62x51mm Ball 11 Long Range", "7.62x54mm R Tungsten Carbide AP"]
    reply = httpx.get("https://escapefromtarkov.fandom.com/api.php", params={
        "action": "query", "titles": "|".join(titles), "prop": "revisions",
        "rvprop": "content|timestamp|ids", "rvslots": "main", "formatversion": 2,
        "format": "json", "redirects": 1,
    }, timeout=30)
    reply.raise_for_status()
    target = Path("artifacts/audit-2026-10-25/sources/wiki-candidates.json")
    target.write_bytes(reply.content)
    print(json.dumps({"url": str(reply.url), "retrieved_at": datetime.now(UTC).isoformat(),
                      "pages": reply.json()}, ensure_ascii=False))


if __name__ == "__main__":
    main()
