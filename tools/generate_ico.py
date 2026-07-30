from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ICON_DIR = ROOT / "src" / "tarkov_armor_sim" / "resources" / "icons"

with Image.open(ICON_DIR / "app-icon.png") as source:
    source.save(
        ICON_DIR / "app-icon.ico",
        format="ICO",
        sizes=((16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)),
    )

