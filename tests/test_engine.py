import pytest

from tarkov_armor_sim.data import SEED_AMMO, default_armor_presets
from tarkov_armor_sim.engine import analyze, simulate
from tarkov_armor_sim.models import ShotScenario
from tarkov_armor_sim.rulesets import CurrentApproximation


def scenario(**kwargs) -> ShotScenario:
    values = {
        "ammo": SEED_AMMO[0],
        "armor_layers": default_armor_presets()["5级陶瓷插板 + 3级软甲"],
        "shot_count": 5,
        "simulation_iterations": 3000,
        "random_seed": 1234,
    }
    values.update(kwargs)
    return ShotScenario(**values)


def test_multilayer_cumulative_probability() -> None:
    result = analyze(scenario(), CurrentApproximation())
    assert len(result.layer_results) == 2
    first, second = result.layer_results
    assert second.cumulative_penetration_probability == pytest.approx(
        first.cumulative_penetration_probability
        * second.conditional_penetration_probability
    )
    assert second.cumulative_penetration_probability <= first.cumulative_penetration_probability


def test_post_penetration_state_decays() -> None:
    result = analyze(scenario(), CurrentApproximation())
    assert result.layer_results[0].remaining_damage < SEED_AMMO[0].damage
    assert result.layer_results[0].remaining_penetration < SEED_AMMO[0].penetration_power


def test_distance_reduces_result() -> None:
    near = analyze(scenario(distance_m=0), CurrentApproximation())
    far = analyze(scenario(distance_m=500), CurrentApproximation())
    assert far.final_penetration_probability < near.final_penetration_probability


def test_fixed_seed_is_reproducible() -> None:
    one = simulate(scenario(), CurrentApproximation())
    two = simulate(scenario(), CurrentApproximation())
    assert one.penetration_probability_by_shot == two.penetration_probability_by_shot
    assert one.kill_probability_by_shot == two.kill_probability_by_shot
    assert one.first_penetration_shot_distribution == two.first_penetration_shot_distribution


def test_monte_carlo_probabilities_and_durability_are_valid() -> None:
    result = simulate(scenario(), CurrentApproximation())
    assert all(0 <= p <= 1 for p in result.penetration_probability_by_shot)
    assert all(0 <= p <= 1 for p in result.kill_probability_by_shot)
    assert all(value >= 0 for snap in result.durability_timeline for value in snap.durability)


def test_projectiles_do_not_reach_backing_layer_when_stopped() -> None:
    result = analyze(scenario(), CurrentApproximation())
    assert result.final_penetration_probability <= result.layer_results[0].conditional_penetration_probability


def test_shotgun_projectile_count_is_preserved() -> None:
    buckshot = next(ammo for ammo in SEED_AMMO if ammo.id == "buckshot")
    assert buckshot.projectile_count == 8

