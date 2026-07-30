from __future__ import annotations

from collections.abc import Callable

import numpy as np

from .models import (
    DurabilitySnapshot,
    LayerResult,
    ProjectileState,
    ShotScenario,
    SimulationResult,
)
from .rulesets import BallisticsRuleset


def distance_adjusted_state(scenario: ShotScenario, *, experimental: bool = False) -> ProjectileState:
    factor = 1.0
    if scenario.enable_distance_decay and scenario.distance_m > 0:
        scale = 0.0009 if experimental else 0.00055
        factor = max(0.58, 1.0 - scale * scenario.distance_m)
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
    layer_results: list[LayerResult] = []
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
        layer_results.append(
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
    health = cumulative * projectile.remaining_damage
    probabilities = [cumulative]
    timeline = [DurabilitySnapshot(0, tuple(layer.current_durability for layer in layers))]
    # Expected-value degradation for instant multi-shot feedback. Monte Carlo remains the
    # authoritative stochastic mode for distributions and kill probability.
    expected_layers = [layer.clone() for layer in layers]
    for layer, detail in zip(expected_layers, layer_results, strict=True):
        layer.current_durability = detail.expected_durability_after
    timeline.append(DurabilitySnapshot(1, tuple(x.current_durability for x in expected_layers)))
    for shot in range(2, scenario.shot_count + 1):
        state = distance_adjusted_state(
            scenario, experimental=ruleset.metadata.confidence.value == "实验性"
        )
        shot_cumulative = 1.0
        for layer in expected_layers:
            probability = ruleset.penetration_probability(state, layer)
            penetrated_loss = ruleset.calculate_armor_damage(state, layer, True)
            stopped_loss = ruleset.calculate_armor_damage(state, layer, False)
            layer.current_durability = max(
                0.0,
                layer.current_durability
                - probability * penetrated_loss
                - (1.0 - probability) * stopped_loss,
            )
            shot_cumulative *= probability
            state = ruleset.calculate_post_penetration_state(state, layer)
        probabilities.append(shot_cumulative)
        timeline.append(
            DurabilitySnapshot(shot, tuple(layer.current_durability for layer in expected_layers))
        )
    first_distribution: dict[int, float] = {}
    chance_not_yet = 1.0
    for shot, probability in enumerate(probabilities, 1):
        first_distribution[shot] = chance_not_yet * probability
        chance_not_yet *= 1.0 - probability
    return SimulationResult(
        final_penetration_probability=cumulative,
        expected_health_damage=health,
        expected_blunt_damage=blunt,
        expected_total_damage=health + blunt,
        layer_results=layer_results,
        durability_timeline=timeline,
        first_penetration_shot_distribution=first_distribution,
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
    rng = np.random.default_rng(scenario.random_seed)
    n = scenario.simulation_iterations
    layers = [layer.clone() for layer in scenario.armor_layers if layer.enabled]
    durability = np.tile(np.array([x.current_durability for x in layers]), (n, 1))
    alive_projectile = np.ones(n, dtype=bool)
    first = np.zeros(n, dtype=np.int16)
    total_health = np.zeros(n)
    total_blunt = np.zeros(n)
    probability_by_shot: list[float] = []
    kill_by_shot: list[float] = []
    timeline = [DurabilitySnapshot(0, tuple(np.mean(durability, axis=0)))]
    initial = distance_adjusted_state(
        scenario, experimental=ruleset.metadata.confidence.value == "实验性"
    )

    for shot in range(1, scenario.shot_count + 1):
        if cancelled and cancelled():
            raise RuntimeError("模拟已取消")
        shot_penetrated = np.zeros(n, dtype=bool)
        shot_damage = np.full(n, initial.remaining_damage)
        shot_pen = np.full(n, initial.remaining_penetration)
        active = alive_projectile.copy()
        for idx, layer in enumerate(layers):
            if not np.any(active):
                break
            # Vector form of the current approximation.
            ratio = np.clip(durability[:, idx] / layer.original_max_durability, 0, 1)
            effective_class = layer.armor_class * (0.55 + 0.45 * ratio)
            prob = np.clip(1 / (1 + np.exp(-(shot_pen - effective_class * 10) / 4.5)), 0.01, 0.99)
            penetrated = (rng.random(n) < prob) & active
            stopped = active & ~penetrated
            blunt = shot_damage * layer.blunt_throughput * max(0.55, 1 - (len(layers) - idx - 1) * 0.08)
            total_blunt += np.where(stopped, blunt, 0)
            energy = np.maximum(0.35, shot_pen / (layer.armor_class * 10))
            loss = np.maximum(
                0.1,
                shot_pen
                * 0.1
                * layer.destructibility
                * energy
                * np.where(penetrated, 0.75, 1.15),
            )
            durability[:, idx] = np.maximum(0, durability[:, idx] - np.where(active, loss, 0))
            ratio_after = np.clip(durability[:, idx] / layer.original_max_durability, 0, 1)
            shot_damage = np.where(
                penetrated,
                shot_damage * (1 - np.minimum(0.42, 0.10 + layer.armor_class * 0.025 + ratio_after * 0.05)),
                shot_damage,
            )
            shot_pen = np.where(
                penetrated,
                np.maximum(0, shot_pen - layer.armor_class * (2.8 + ratio_after)),
                shot_pen,
            )
            active = penetrated
        shot_penetrated = active
        first[(first == 0) & shot_penetrated] = shot
        total_health += np.where(shot_penetrated, shot_damage, 0)
        probability_by_shot.append(float(np.mean(shot_penetrated)))
        kill_by_shot.append(float(np.mean(total_health >= 85)))
        timeline.append(DurabilitySnapshot(shot, tuple(np.mean(durability, axis=0))))
        if progress:
            progress(round(shot / scenario.shot_count * 100))

    dist = {
        shot: float(np.mean(first == shot))
        for shot in range(1, scenario.shot_count + 1)
        if np.any(first == shot)
    }
    analytic = analyze(scenario, ruleset)
    analytic.final_penetration_probability = probability_by_shot[0]
    analytic.expected_health_damage = float(np.mean(total_health))
    analytic.expected_blunt_damage = float(np.mean(total_blunt))
    analytic.expected_total_damage = analytic.expected_health_damage + analytic.expected_blunt_damage
    analytic.durability_timeline = timeline
    analytic.first_penetration_shot_distribution = dist
    analytic.kill_probability_by_shot = kill_by_shot
    analytic.penetration_probability_by_shot = probability_by_shot
    return analytic
