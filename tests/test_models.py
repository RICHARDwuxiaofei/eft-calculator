import pytest

from tarkov_armor_sim.data import SEED_AMMO, default_armor_presets
from tarkov_armor_sim.models import ArmorLayer, ArmorLayerType, ArmorMaterial, ShotScenario


def test_true_durability_uses_factory_maximum() -> None:
    layer = ArmorLayer(
        "x", "维修过的护甲", ArmorLayerType.PLATE, 5, 40, 45, 50,
        ArmorMaterial.CERAMIC, 0.8, 0.1, True,
    )
    assert layer.true_durability_ratio == pytest.approx(0.8)


def test_repair_max_is_not_factory_max() -> None:
    with pytest.raises(ValueError, match="维修上限"):
        ArmorLayer(
            "x", "非法", ArmorLayerType.PLATE, 5, 40, 55, 50,
            ArmorMaterial.STEEL, 0.4, 0.1, True,
        )


@pytest.mark.parametrize("armor_class", [0, 7])
def test_armor_class_validation(armor_class: int) -> None:
    with pytest.raises(ValueError, match="等级"):
        ArmorLayer(
            "x", "非法", ArmorLayerType.PLATE, armor_class, 40, 40, 40,
            ArmorMaterial.STEEL, 0.4, 0.1, True,
        )


def test_scenario_limits_layers() -> None:
    layer = default_armor_presets()["仅3级软甲"][0]
    with pytest.raises(ValueError, match="最多"):
        ShotScenario(SEED_AMMO[0], tuple(layer.clone() for _ in range(13)))

