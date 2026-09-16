"""Independent mathematical anchors, not a claim of in-game validation.

Decimal calculations of the published Desmos equation were recorded independently
of production code; deterministic path cases have hand-computable expectations.
"""
import itertools
import math
from dataclasses import replace

import pytest
from tarkov_sim_core.engine import analyze, simulate
from tarkov_sim_core.models import (
    Ammo,
    ArmorLayer,
    ArmorLayerType,
    ArmorMaterial,
    BodyPart,
    ProjectileState,
    ShotScenario,
)
from tarkov_sim_core.rulesets import MATERIAL_DESTRUCTIBILITY, CurrentApproximation

RULES = CurrentApproximation()


def armor(level=5, current=100.0, repaired=100.0, original=100.0, material=ArmorMaterial.CERAMIC):
    return ArmorLayer("test", "Reference plate", ArmorLayerType.PLATE, level, current,
                      repaired, original, material, MATERIAL_DESTRUCTIBILITY[material.value], .1, True)


def ammo(pen=40.0, damage=50.0, armor_damage=50.0, pellets=1):
    return Ammo("test", "Reference cartridge", "T", "test", damage, pen, armor_damage, pellets)


def scenario(**kwargs):
    values = {"ammo": ammo(), "armor_layers": (armor(),), "shot_count": 1,
                  "simulation_iterations": 20000, "random_seed": 876}
    values.update(kwargs)
    return ShotScenario(**values)


@pytest.mark.parametrize("level,pen,current,expected", [
    (4,40,100,0.8718160099958351),
    (5,40,100,0.08851353602665556),
    (5,40,50,0.5514399524375743),
    (5,40,25,0.9566828156169849),
    (6,53,100,0.2337778592253228),
    (3,30,100,0.8788199750104123),
    (4,55,100,0.9707243417050491),
])
def test_independent_decimal_penetration_anchors(level, pen, current, expected):
    value = RULES.penetration_probability(ProjectileState(50, pen), armor(level, current))
    assert value == pytest.approx(expected, abs=1e-13)


def test_probability_uses_factory_maximum_not_repaired_maximum():
    repaired = armor(5, 45, 45, 90)
    unrepaired = armor(5, 45, 90, 90)
    new = armor(5, 90, 90, 90)
    state = ProjectileState(50,40)
    assert RULES.penetration_probability(state, repaired) == RULES.penetration_probability(state, unrepaired)
    assert RULES.penetration_probability(state, repaired) > RULES.penetration_probability(state, new)


@pytest.mark.parametrize("level", range(1,7))
def test_probability_monotone_in_penetration_and_durability(level):
    for pen in range(0, 121, 4):
        values = [RULES.penetration_probability(ProjectileState(50,pen), armor(level,float(d))) for d in range(101)]
        assert all(a+1e-13 >= b for a,b in itertools.pairwise(values))
        assert all(0 <= p <= 1 for p in values)
    for current in (1,25,50,100):
        values = [RULES.penetration_probability(ProjectileState(50,pen), armor(level,current)) for pen in range(121)]
        assert all(a <= b+1e-13 for a,b in itertools.pairwise(values))


def test_no_artificial_one_percent_floor_or_99_percent_broken_cap():
    assert RULES.penetration_probability(ProjectileState(50,1),armor(6)) == 0
    assert RULES.penetration_probability(ProjectileState(50,0),armor(6,0)) == 1


def test_material_does_not_change_initial_penetration_but_changes_wear():
    state = ProjectileState(50,40,armor_damage_percent=60)
    ceramic, aramid = armor(), armor(material=ArmorMaterial.ARAMID)
    assert RULES.penetration_probability(state,ceramic) == RULES.penetration_probability(state,aramid)
    assert RULES.calculate_armor_damage(state,ceramic,False) > RULES.calculate_armor_damage(state,aramid,False)


def test_ammo_armor_damage_percent_is_not_ignored():
    low = ProjectileState(50,40,armor_damage_percent=20)
    high = replace(low, armor_damage_percent=60)
    assert RULES.calculate_armor_damage(high,armor(),False) == pytest.approx(3*RULES.calculate_armor_damage(low,armor(),False))
    assert RULES.penetration_probability(low,armor()) == RULES.penetration_probability(high,armor())


def test_broken_armor_never_blocks_reduces_or_takes_damage():
    result = analyze(scenario(armor_layers=(armor(6,0),)),RULES)
    assert result.final_penetration_probability == 1
    assert result.expected_health_damage == 50
    assert result.expected_blunt_damage == 0
    assert result.layer_results[0].expected_durability_loss == 0


def test_fully_blocked_front_layer_never_damages_backing():
    value = analyze(scenario(ammo=ammo(pen=0),armor_layers=(armor(),armor(3))),RULES)
    assert value.layer_results[0].expected_durability_loss == 1
    assert value.layer_results[1].expected_durability_loss == 0
    assert value.durability_timeline[-1].durability[1] == 100


def test_sequential_all_pellets_hit_and_break_armor_mid_shell():
    # Four 0-pen pellets each remove the minimum 1 point; remaining four hit unarmored.
    s = scenario(ammo=ammo(pen=0, pellets=8),armor_layers=(armor(6,4),),simulation_iterations=20)
    result = simulate(s,RULES)
    assert result.final_penetration_probability == 1
    assert result.expected_health_damage == 4*50
    assert result.durability_timeline[-1].durability == (0,)
    assert result.expected_blunt_damage > 0


def test_single_and_monte_carlo_agree_with_sampling_error():
    s = scenario()
    exact, sampled = analyze(s,RULES), simulate(s,RULES)
    p = exact.final_penetration_probability
    sigma = math.sqrt(p*(1-p)/s.simulation_iterations)
    assert abs(sampled.final_penetration_probability-p) < 5*sigma
    assert sampled.expected_health_damage == pytest.approx(exact.expected_health_damage, abs=.45)
    assert sampled.expected_blunt_damage == pytest.approx(exact.expected_blunt_damage, abs=.08)


def test_first_trigger_and_burst_damage_are_separate_and_consistent():
    s = scenario(armor_layers=(),shot_count=3,simulation_iterations=10)
    result = simulate(s,RULES)
    assert result.expected_health_damage == 50
    assert result.expected_burst_health_damage == 150
    assert result.expected_burst_total_damage == sum(result.health_damage_by_shot)+sum(result.blunt_damage_by_shot)
    assert result.three_shot_penetration_probability == 1
    assert sum(result.first_penetration_shot_distribution.values()) == 1


def test_three_shot_probability_sums_exclusive_first_events_not_marginals():
    result = simulate(scenario(shot_count=5,simulation_iterations=1000),RULES)
    assert result.three_shot_penetration_probability == pytest.approx(sum(result.first_penetration_shot_distribution.get(s,0) for s in (1,2,3)))
    assert result.three_shot_penetration_probability >= result.final_penetration_probability
    assert sum(result.first_penetration_shot_distribution.values()) <= 1+1e-12


def test_stomach_is_not_treated_as_70_hp_instant_death():
    result = simulate(scenario(body_part=BodyPart.STOMACH,ammo=ammo(damage=200),armor_layers=(),simulation_iterations=10),RULES)
    assert not result.kill_estimate_supported
    assert result.kill_probability_by_shot == []


def test_disabled_layers_have_no_timeline_column():
    a,b=armor(),armor(3)
    a.enabled=False
    result=analyze(scenario(armor_layers=(a,b)),RULES)
    assert len(result.layer_results)==1
    assert all(len(s.durability)==1 for s in result.durability_timeline)


@pytest.mark.parametrize("bad", [float('nan'),float('inf'),-float('inf'),True])
def test_non_finite_inputs_are_rejected(bad):
    with pytest.raises((ValueError,TypeError)):
        ammo(pen=bad)
    with pytest.raises((ValueError,TypeError)):
        armor(current=bad)


def test_unimplemented_switches_fail_instead_of_silently_lying():
    with pytest.raises(ValueError): scenario(enable_fragmentation=True)
    with pytest.raises(ValueError): scenario(enable_skills=True)


def test_zero_observed_penetrations_do_not_get_zero_width_confidence_interval():
    result=simulate(scenario(ammo=ammo(pen=0),simulation_iterations=100),RULES)
    low,high=result.penetration_confidence_interval
    assert low < 1e-12
    assert 0 < high < .05


def test_models_are_not_mutated_by_calculation():
    s=scenario(shot_count=3,simulation_iterations=200)
    before=[a.__dict__.copy() for a in s.armor_layers]
    simulate(s,RULES)
    assert before == [a.__dict__ for a in s.armor_layers]
