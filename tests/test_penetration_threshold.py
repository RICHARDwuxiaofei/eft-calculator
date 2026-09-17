from __future__ import annotations

import pytest
from tarkov_sim_core.models import ArmorLayer, ArmorLayerType, ArmorMaterial, ProjectileState
from tarkov_sim_core.rulesets import CurrentApproximation, armor_resistance


def _plate(*, armor_class: int = 4, current: float = 100.0) -> ArmorLayer:
    return ArmorLayer(
        "threshold-plate",
        "Threshold reference plate",
        ArmorLayerType.PLATE,
        armor_class,
        current,
        100.0,
        100.0,
        ArmorMaterial.STEEL,
        0.525,
        0.1,
        True,
    )


@pytest.mark.parametrize("armor_class,current", [(2, 100.0), (4, 100.0), (5, 50.0), (6, 25.0)])
def test_plus_fifteen_over_effective_durability_is_guaranteed(
    armor_class: int, current: float
) -> None:
    rules = CurrentApproximation()
    plate = _plate(armor_class=armor_class, current=current)
    resistance = armor_resistance(plate)

    guaranteed = rules.penetration_probability(
        ProjectileState(50.0, resistance + 15.0), plate
    )
    just_below = rules.penetration_probability(
        ProjectileState(50.0, resistance + 14.999), plate
    )

    assert guaranteed == 1.0
    assert 0.0 <= just_below < 1.0
