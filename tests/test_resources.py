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
