from __future__ import annotations

import argparse
import json
from pathlib import Path

import httpx

AMMO_URL = "https://raw.githubusercontent.com/TarkovTracker/tarkovdata/master/ammunition.json"
ASSET_URL = "https://assets.tarkov.dev/{item_id}-icon.webp"
DEFAULT_OUTPUT = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "tarkov_armor_sim"
    / "resources"
    / "items"
    / "ammo-live"
)


def fetch(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        response = client.get(AMMO_URL)
        response.raise_for_status()
        records = response.json()
        manifest: dict[str, dict[str, str]] = {}
        missing: list[str] = []
        for item_id, record in sorted(records.items()):
            url = ASSET_URL.format(item_id=item_id)
            target = output / f"{item_id}.webp"
            image = client.get(url)
            if image.status_code == 404:
                missing.append(item_id)
                continue
            image.raise_for_status()
            if not image.headers.get("content-type", "").startswith("image/"):
                raise RuntimeError(f"Unexpected content type for {item_id}: {url}")
            target.write_bytes(image.content)
            manifest[item_id] = {
                "name": record.get("name") or item_id,
                "short_name": record.get("shortName") or record.get("name") or item_id,
                "source_url": url,
            }
    (output / "manifest.json").write_text(
        json.dumps(
            {
                "data_source": AMMO_URL,
                "image_source_pattern": ASSET_URL,
                "missing_image_ids": missing,
                "items": manifest,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch current EFT ammo inventory icons.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    fetch(parser.parse_args().output)
