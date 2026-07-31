from __future__ import annotations

import random
from collections.abc import Callable

from ..models import (
    DurabilitySnapshot,
    LayerResult,
    ProjectileState,
    ShotScenario,
    SimulationResult,
)
from ..rulesets import BallisticsRuleset


def distance_adjusted_state(
    scenario: ShotScenario, *, experimental: bool = False
) -> ProjectileState:
    factor = 1.0
    if scenario.enable_distance_decay and scenario.distance_m > 0:
        factor = max(0.58, 1.0 - (0.0009 if experimental else 0.00055) * scenario.distance_m)
    return ProjectileState(
        remaining_damage=scenario.ammo.damage * factor,
        remaining_penetration=scenario.ammo.penetration_power * factor,
    )


def analyze(scenario: ShotScenario, ruleset: BallisticsRuleset) -> SimulationResult:
    projectile = distance_adjusted_state(
        scenario, experimental=ruleset.metadata.confidence.value == "实验性"
    )
    cumulative = 1.0
    blunt = 0.0
    details: list[LayerResult] = []
    layers = [layer for layer in scenario.armor_layers if layer.enabled]
    for index, layer in enumerate(layers):
        conditional = ruleset.penetration_probability(projectile, layer)
        stop = cumulative * (1.0 - conditional)
        loss_pen = ruleset.calculate_armor_damage(projectile, layer, True)
        loss_stop = ruleset.calculate_armor_damage(projectile, layer, False)
        expected_loss = conditional * loss_pen + (1.0 - conditional) * loss_stop
        blunt += stop * ruleset.calculate_blunt_damage(projectile, layer, layers[index + 1 :])
        cumulative *= conditional
        projectile = ruleset.calculate_post_penetration_state(projectile, layer)
        details.append(
            LayerResult(
                name=layer.name,
                conditional_penetration_probability=conditional,
                cumulative_penetration_probability=cumulative,
                stop_probability=stop,
                expected_durability_loss=expected_loss,
                expected_durability_after=max(0.0, layer.current_durability - expected_loss),
                remaining_damage=projectile.remaining_damage,
                remaining_penetration=projectile.remaining_penetration,
            )
        )
    projectile_probability = cumulative
    cumulative = 1.0 - (1.0 - projectile_probability) ** scenario.ammo.projectile_count
    health = (
        projectile_probability
        * projectile.remaining_damage
        * scenario.ammo.projectile_count
    )
    blunt *= scenario.ammo.projectile_count
    probabilities = [cumulative]
    timeline = [DurabilitySnapshot(0, tuple(layer.current_durability for layer in layers))]
    expected_layers = [layer.clone() for layer in layers]
    for layer, detail in zip(expected_layers, details):
        expected_loss = layer.current_durability - detail.expected_durability_after
        layer.current_durability = max(
            0.0,
            layer.current_durability - expected_loss * scenario.ammo.projectile_count,
        )
    timeline.append(DurabilitySnapshot(1, tuple(layer.current_durability for layer in expected_layers)))
    for shot in range(2, scenario.shot_count + 1):
        state = distance_adjusted_state(
            scenario, experimental=ruleset.metadata.confidence.value == "实验性"
        )
        shot_probability = 1.0
        for layer in expected_layers:
            probability = ruleset.penetration_probability(state, layer)
            loss = (
                probability * ruleset.calculate_armor_damage(state, layer, True)
                + (1.0 - probability) * ruleset.calculate_armor_damage(state, layer, False)
            )
            layer.current_durability = max(
                0.0,
                layer.current_durability - loss * scenario.ammo.projectile_count,
            )
            shot_probability *= probability
            state = ruleset.calculate_post_penetration_state(state, layer)
        probabilities.append(
            1.0 - (1.0 - shot_probability) ** scenario.ammo.projectile_count
        )
        timeline.append(DurabilitySnapshot(shot, tuple(x.current_durability for x in expected_layers)))
    first: dict[int, float] = {}
    chance_not_yet = 1.0
    for shot, probability in enumerate(probabilities, 1):
        first[shot] = chance_not_yet * probability
        chance_not_yet *= 1.0 - probability
    return SimulationResult(
        final_penetration_probability=cumulative,
        expected_health_damage=health,
        expected_blunt_damage=blunt,
        expected_total_damage=health + blunt,
        layer_results=details,
        durability_timeline=timeline,
        first_penetration_shot_distribution=first,
        kill_probability_by_shot=[float(health >= 85)],
        penetration_probability_by_shot=probabilities,
        confidence=ruleset.metadata.confidence,
        data_version=scenario.ammo.source_version,
        ruleset_version=ruleset.metadata.version,
    )


def simulate(
    scenario: ShotScenario,
    ruleset: BallisticsRuleset,
    progress: Callable[[int], None] | None = None,
    cancelled: Callable[[], bool] | None = None,
) -> SimulationResult:
    """Deterministic portable Monte Carlo implementation using only the Python stdlib."""

    rng = random.Random(scenario.random_seed)
    layers = [layer for layer in scenario.armor_layers if layer.enabled]
    iteration_count = scenario.simulation_iterations
    penetration_counts = [0] * scenario.shot_count
    kill_counts = [0] * scenario.shot_count
    first_counts = [0] * (scenario.shot_count + 1)
    total_health_sum = 0.0
    total_blunt_sum = 0.0
    durability_sums = [[0.0 for _ in layers] for _ in range(scenario.shot_count + 1)]

    for iteration in range(iteration_count):
        if cancelled and cancelled():
            raise RuntimeError("模拟已取消")
        durability = [layer.current_durability for layer in layers]
        total_health = 0.0
        total_blunt = 0.0
        first_shot = 0
        for idx, value in enumerate(durability):
            durability_sums[0][idx] += value
        for shot in range(scenario.shot_count):
            penetrated_this_shot = False
            for _projectile in range(scenario.ammo.projectile_count):
                state = distance_adjusted_state(
                    scenario, experimental=ruleset.metadata.confidence.value == "实验性"
                )
                penetrated_all = True
                for layer_index, template in enumerate(layers):
                    layer = template.clone()
                    layer.current_durability = durability[layer_index]
                    probability = ruleset.penetration_probability(state, layer)
                    penetrated = rng.random() < probability
                    durability[layer_index] = max(
                        0.0,
                        durability[layer_index]
                        - ruleset.calculate_armor_damage(state, layer, penetrated),
                    )
                    if not penetrated:
                        total_blunt += ruleset.calculate_blunt_damage(
                            state, layer, layers[layer_index + 1 :]
                        )
                        penetrated_all = False
                        break
                    state = ruleset.calculate_post_penetration_state(state, layer)
                if penetrated_all:
                    penetrated_this_shot = True
                    total_health += state.remaining_damage
            if penetrated_this_shot:
                penetration_counts[shot] += 1
                if first_shot == 0:
                    first_shot = shot + 1
            if total_health >= 85:
                kill_counts[shot] += 1
            for idx, value in enumerate(durability):
                durability_sums[shot + 1][idx] += value
        first_counts[first_shot] += 1
        total_health_sum += total_health
        total_blunt_sum += total_blunt
        if progress and (iteration + 1) % max(1, iteration_count // 100) == 0:
            progress(round((iteration + 1) / iteration_count * 100))

    analytic = analyze(scenario, ruleset)
    probabilities = [count / iteration_count for count in penetration_counts]
    analytic.final_penetration_probability = probabilities[0]
    analytic.expected_health_damage = total_health_sum / iteration_count
    analytic.expected_blunt_damage = total_blunt_sum / iteration_count
    analytic.expected_total_damage = (
        analytic.expected_health_damage + analytic.expected_blunt_damage
    )
    analytic.durability_timeline = [
        DurabilitySnapshot(
            shot,
            tuple(value / iteration_count for value in durability_sums[shot]),
        )
        for shot in range(scenario.shot_count + 1)
    ]
    analytic.first_penetration_shot_distribution = {
        shot: first_counts[shot] / iteration_count
        for shot in range(1, scenario.shot_count + 1)
        if first_counts[shot]
    }
    analytic.kill_probability_by_shot = [count / iteration_count for count in kill_counts]
    analytic.penetration_probability_by_shot = probabilities
    return analytic
