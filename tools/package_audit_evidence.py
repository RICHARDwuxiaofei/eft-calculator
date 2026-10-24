"""Collect public audit evidence and verify delivered offline assets without changing data."""
from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT/"artifacts/audit-2026-10-25"
TARGET = ROOT/"docs/audits/2026-10-25"
ITEMS = ROOT/"src/tarkov_armor_sim/resources/items"


def main():
    TARGET.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((ITEMS/"image-manifest.json").read_text(encoding="utf-8"))
    packaging = []
    for variant in ("debug", "release"):
        apk = ROOT/f"android/app/build/outputs/apk/{variant}/app-{variant}{'-unsigned' if variant == 'release' else ''}.apk"
        with zipfile.ZipFile(apk) as archive:
            for item in manifest["items"].values():
                assert hashlib.sha256(archive.read("assets/"+item["path"])).hexdigest() == item["sha256"]
            assert archive.read("assets/catalog.json") == (ITEMS/"catalog.json").read_bytes()
        packaging.append({"variant":variant,"file":str(apk.relative_to(ROOT)),"sha256":hashlib.sha256(apk.read_bytes()).hexdigest(),"verified_images":222,"catalog_identical":True,"signing":"debug key" if variant == "debug" else "unsigned: NOT a delivery APK"})
    bundled = ROOT/"dist/TarkovArmorSimulator/_internal/tarkov_armor_sim/resources/items"
    for item in manifest["items"].values():
        assert hashlib.sha256((bundled/item["path"]).read_bytes()).hexdigest() == item["sha256"]
    assert (bundled/"catalog.json").read_bytes() == (ITEMS/"catalog.json").read_bytes()
    packaging.append({"variant":"windows","verified_images":222,"catalog_identical":True,"signing":"not Authenticode signed"})
    (SOURCE/"packaging.json").write_text(json.dumps(packaging,indent=2)+"\n",encoding="utf-8")
    files = ["inventory.json","item-pages.json","applied-data-diff.json","numerical.json","online-images.json","packaging.json","pytest.xml"]
    files += [str(path.relative_to(SOURCE)) for path in SOURCE.glob("image-contact-*.png")]
    for folder in ("ui/before","ui/after","android-runtime","android-before","android-dark","windows-runtime"):
        files += [str(path.relative_to(SOURCE)) for path in (SOURCE/folder).glob("*") if path.suffix in (".png", ".xml", ".json") or path.name == "instrumentation.txt"]
    for relative in files:
        target = TARGET/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        source = SOURCE/relative
        if source.suffix in (".json", ".xml", ".txt"):
            target.write_bytes(source.read_bytes().replace(b"\r\n", b"\n"))
        else:
            shutil.copy2(source,target)
    source_manifest = json.loads((SOURCE/"sources/manifest.json").read_text(encoding="utf-8"))
    # Retain status/hash evidence for failed pages, not anti-bot challenge HTML/tokens.
    for value in source_manifest["sources"].values():
        value.pop("error", None)
    source_manifest["game_version"] = "Wiki-reported 1.2.5.0.48146 (20 October 2026); official site inaccessible"
    (TARGET/"sources.json").write_bytes((json.dumps(source_manifest,ensure_ascii=False,indent=2)+"\n").encode("utf-8"))
    with zipfile.ZipFile(TARGET/"public-source-snapshots.zip","w",zipfile.ZIP_DEFLATED) as archive:
        for path in (SOURCE/"sources").glob("*"):
            if path.name.startswith(("wiki-api-", "wiki-items-", "wiki-ammo-", "wiki-candidates")) or path.name == "nofood-chart.html":
                archive.write(path, path.name)
    hashes = {str(path.relative_to(TARGET)).replace("\\", "/"):hashlib.sha256(path.read_bytes()).hexdigest()
              for path in TARGET.rglob("*") if path.is_file() and path.name != "evidence-sha256.json"}
    (TARGET/"evidence-sha256.json").write_bytes((json.dumps(hashes,indent=2)+"\n").encode("utf-8"))
    print(json.dumps({"packaging":packaging,"evidence_files":len(hashes)},indent=2))


if __name__ == "__main__":
    main()
