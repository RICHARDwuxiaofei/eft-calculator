from PySide6.QtGui import QImage

from tarkov_armor_sim.data import SEED_AMMO
from tarkov_armor_sim.ui import resource_path


def test_all_seed_ammo_have_icons() -> None:
    missing = [
        ammo.id
        for ammo in SEED_AMMO
        if not resource_path("items", "ammo", f"{ammo.id}.png").exists()
    ]
    assert missing == []


def test_armor_and_application_icons_exist() -> None:
    for name in (
        "ceramic",
        "steel",
        "uhmwpe",
        "aramid",
        "titanium",
        "helmet",
    ):
        assert resource_path("items", "armor", f"{name}.png").exists()
    assert resource_path("items", "armor", "combined.webp").exists()
    assert resource_path("items", "armor", "uhmwpe-kiteco.png").exists()
    assert resource_path("icons", "app-icon.ico").exists()
    app_icon = QImage(str(resource_path("icons", "app-icon.png")))
    assert not app_icon.isNull()
    assert app_icon.hasAlphaChannel()


def test_live_ammo_icons_are_item_specific() -> None:
    live = resource_path("items", "ammo-live")
    icons = list(live.glob("*.webp"))
    assert len(icons) >= 150
    m855 = QImage(str(live / "54527a984bdc2d4e668b4567.webp"))
    ap20 = QImage(str(live / "5d6e68a8a4b9360b6c0d54e2.webp"))
    assert not m855.isNull()
    assert not ap20.isNull()
    assert (live / "54527a984bdc2d4e668b4567.webp").read_bytes() != (
        live / "5d6e68a8a4b9360b6c0d54e2.webp"
    ).read_bytes()
