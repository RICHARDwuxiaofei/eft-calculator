from __future__ import annotations

import json
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

import httpx
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
RESOURCE_ROOT = ROOT / "src" / "tarkov_armor_sim" / "resources" / "items"
API = "https://escapefromtarkov.fandom.com/api.php"

ASSETS = {
    "ammo/m855a1.png": "File:M855A1ICON.png",
    "ammo/m855.png": "File:M855ICON.png",
    "ammo/m995.png": "File:M995.png",
    "ammo/762bp.png": "File:7.62x39BP_ins.png",
    "ammo/7n40.png": "File:7N40 Full.png",
    "ammo/545bp.png": "File:AKBPIMAGE.png",
    "ammo/m80.png": "File:M80ICON.png",
    "ammo/ap20.png": "File:12-70 AP-20.png",
    "ammo/buckshot.png": "File:12x70BUCKSHOTIMAGE.png",
    "armor/ceramic.png": "File:KITECO SC-IV SA ballistic plate icon.png",
    "armor/steel.png": "File:Global Armor's Steel ballistic plate icon.png",
    "armor/uhmwpe.png": "File:Monoclete level III PE ballistic plate icon.png",
    "armor/aramid.png": "File:PACA Soft Armor.png",
    "armor/titanium.png": "File:Kiba Arms Titan Ballistic plate icon.png",
    "armor/combined.png": "File:ESAPI level IV ballistic plate icon.png",
    "armor/helmet.png": "File:Kiver-M Helmet icon.png",
}


def main() -> int:
    RESOURCE_ROOT.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, object]] = []
    headers = {"User-Agent": "EFT-Calculator/1.0 (open-source desktop utility)"}
    with httpx.Client(headers=headers, follow_redirects=True, timeout=30) as client:
        for relative_path, wiki_title in ASSETS.items():
            response = client.get(
                API,
                params={
                    "action": "query",
                    "titles": wiki_title,
                    "prop": "imageinfo",
                    "iiprop": "url|mime|size",
                    "format": "json",
                },
            )
            response.raise_for_status()
            page = next(iter(response.json()["query"]["pages"].values()))
            if "missing" in page or not page.get("imageinfo"):
                raise RuntimeError(f"Wiki image is missing: {wiki_title}")
            image_info = page["imageinfo"][0]
            image_response = client.get(image_info["url"])
            image_response.raise_for_status()
            with Image.open(BytesIO(image_response.content)) as source:
                image = source.convert("RGBA")
                image.thumbnail((128, 128), Image.Resampling.LANCZOS)
                target = RESOURCE_ROOT / relative_path
                target.parent.mkdir(parents=True, exist_ok=True)
                image.save(target, "PNG", optimize=True)
            records.append(
                {
                    "path": relative_path,
                    "wiki_title": wiki_title,
                    "description_url": image_info["descriptionurl"],
                    "original_url": image_info["url"],
                    "original_size": image_info.get("size"),
                }
            )
            print(f"Downloaded {wiki_title} -> {relative_path}")

    metadata = {
        "retrieved_at": datetime.now(UTC).isoformat(),
        "source": "Escape from Tarkov Wiki via MediaWiki API",
        "source_api": API,
        "notice": (
            "These item images are third-party game reference assets and are not licensed "
            "under this project's MIT License. Rights remain with their respective owners."
        ),
        "assets": records,
    }
    (RESOURCE_ROOT / "sources.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
