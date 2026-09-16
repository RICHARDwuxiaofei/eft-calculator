from __future__ import annotations

import math
import random
from collections.abc import Callable
from dataclasses import replace

from ..models import (
    BodyPart,
    CalculationConfidence,
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
        # Retained for sensitivity studies ONLY; explicitly flagged in every result.
        factor = max(0.58, 1.0 - (0.0009 if experimental else 0.00055) * scenario.distance_m)
    return ProjectileState(
        remaining_damage=scenario.ammo.damage * factor,
        remaining_penetration=scenario.ammo.penetration_power * factor,
        armor_damage_percent=scenario.ammo.armor_damage_percent,
    )


def _health_limit(scenario: ShotScenario) -> float | None:
    # Stomach destruction is not death. Black-limb redistribution is not modeled.
    return {BodyPart.THORAX: 85.0, BodyPart.HEAD: 35.0}.get(scenario.body_part)


def _initial(scenario: ShotScenario, ruleset: BallisticsRuleset) -> ProjectileState:
    return distance_adjusted_state(
        scenario, experimental=ruleset.metadata.confidence == CalculationConfidence.EXPERIMENTAL
    )


def _annotate(result: SimulationResult, scenario: ShotScenario) -> SimulationResult:
    result.kill_estimate_supported = _health_limit(scenario) is not None
    if not result.kill_estimate_supported:
        result.kill_probability_by_shot = []
        result.warnings.append("Stomach: no death prediction; black-limb overflow is not modeled.")
    if scenario.distance_m > 0:
        if scenario.enable_distance_decay:
            result.confidence = CalculationConfidence.EXPERIMENTAL
            result.warnings.append("Distance decay is a linear sensitivity estimate, NOT verified EFT flight physics.")
        else:
            result.warnings.append("Distance decay disabled: calculations use muzzle damage/penetration.")
    if len([a for a in scenario.armor_layers if a.enabled]) > 1:
        result.warnings.append("Backing-soft-armor blunt attenuation is not modeled; blunt damage is approximate.")
    result.warnings.append("All pellets hit this same chosen armor path; no spread or partial-hit selection.")
    return result


def _single(scenario: ShotScenario, ruleset: BallisticsRuleset) -> SimulationResult:
    """Exact expectation for ONE projectile under the selected deterministic loss model."""
    state = _initial(scenario, ruleset)
    layers = [layer for layer in scenario.armor_layers if layer.enabled]
    reach, blunt, kill = 1.0, 0.0, 0.0
    details: list[LayerResult] = []
    threshold = _health_limit(scenario)
    for index, layer in enumerate(layers):
        probability = ruleset.penetration_probability(state, layer)
        stopped = reach * (1.0 - probability)
        blunt_damage = ruleset.calculate_blunt_damage(state, layer, layers[index + 1:])
        blunt += stopped * blunt_damage
        if threshold is not None and blunt_damage >= threshold:
            kill += stopped
        # Crucial: only projectiles that REACH a layer can damage that layer.
        # Clamp each branch before averaging (not the other way around).
        loss = reach * (
            probability * min(layer.current_durability,
                              ruleset.calculate_armor_damage(state, layer, True))
            + (1.0 - probability) * min(layer.current_durability,
                                       ruleset.calculate_armor_damage(state, layer, False))
        )
        reach *= probability
        state = ruleset.calculate_post_penetration_state(state, layer)
        details.append(LayerResult(
            name=layer.name,
            conditional_penetration_probability=probability,
            cumulative_penetration_probability=reach,
            stop_probability=stopped,
            expected_durability_loss=loss,
            expected_durability_after=max(0.0, layer.current_durability - loss),
            remaining_damage=state.remaining_damage,
            remaining_penetration=state.remaining_penetration,
        ))
    health = reach * state.remaining_damage
    if threshold is not None and state.remaining_damage >= threshold:
        kill += reach
    return _annotate(SimulationResult(
        final_penetration_probability=reach,
        expected_health_damage=health,
        expected_blunt_damage=blunt,
        expected_total_damage=health + blunt,
        expected_burst_health_damage=health,
        expected_burst_blunt_damage=blunt,
        expected_burst_total_damage=health + blunt,
        health_damage_by_shot=[health],
        blunt_damage_by_shot=[blunt],
        layer_results=details,
        durability_timeline=[
            DurabilitySnapshot(0, tuple(layer.current_durability for layer in layers)),
            DurabilitySnapshot(1, tuple(detail.expected_durability_after for detail in details)),
        ],
        first_penetration_shot_distribution={1: reach},
        kill_probability_by_shot=[min(1.0, kill)],
        penetration_probability_by_shot=[reach],
        penetration_confidence_interval=(reach, reach),
        confidence=ruleset.metadata.confidence,
        data_version=scenario.ammo.source_version,
        ruleset_version=ruleset.metadata.version,
    ), scenario)


def analyze(scenario: ShotScenario, ruleset: BallisticsRuleset) -> SimulationResult:
    """Exact single-shot single-projectile result; seeded sampling for dependent histories.

    No plug-in mean durability, independence assumption, or multiply-by-pellet shortcut.
    Sampling uncertainty is returned separately from uncertainty in the game model.
    """
    if scenario.shot_count == 1 and scenario.ammo.projectile_count == 1:
        return _single(scenario, ruleset)
    preview = replace(scenario, simulation_iterations=min(scenario.simulation_iterations, 4096),
                      random_seed=scenario.random_seed if scenario.random_seed is not None else 20260916)
    result = simulate(preview, ruleset)
    result.method = "seeded-trajectory-preview"
    return result


def _wilson(successes: int, total: int) -> tuple[float, float]:
    z = 1.959963984540054
    p = successes / total
    scale = 1 + z * z / total
    center = (p + z * z / (2 * total)) / scale
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / scale
    return max(0.0, center - half), min(1.0, center + half)


def simulate(
    scenario: ShotScenario,
    ruleset: BallisticsRuleset,
    progress: Callable[[int], None] | None = None,
    cancelled: Callable[[], bool] | None = None,
) -> SimulationResult:
    """Sequential pellets/shots with independent per-trial armor state.

    Metrics are PER FIRST TRIGGER PULL in both modes. Explicit burst fields carry
    the whole string of shots. Damage is potential uncapped damage, not corpse HP.
    """
    rng = random.Random(scenario.random_seed if scenario.random_seed is not None else 20260916)
    templates = [layer for layer in scenario.armor_layers if layer.enabled]
    count, shots = scenario.simulation_iterations, scenario.shot_count
    penetration_counts, kill_counts, first_counts = [0] * shots, [0] * shots, [0] * (shots + 1)
    health_sums, blunt_sums = [0.0] * shots, [0.0] * shots
    durability_sums = [[0.0] * len(templates) for _ in range(shots + 1)]
    threshold = _health_limit(scenario)
    initial = _initial(scenario, ruleset)

    for iteration in range(count):
        if cancelled and cancelled():
            raise RuntimeError("Simulation cancelled")
        layers = [layer.clone() for layer in templates]
        cumulative_damage, first_shot = 0.0, 0
        for shot in range(shots):
            penetrated_shot = False
            shot_health, shot_blunt = 0.0, 0.0
            for _ in range(scenario.ammo.projectile_count):
                state = replace(initial)
                for index, layer in enumerate(layers):
                    if layer.current_durability <= 0:
                        continue
                    probability = ruleset.penetration_probability(state, layer)
                    penetrated = rng.random() < probability
                    loss = ruleset.calculate_armor_damage(state, layer, penetrated)
                    # Both damage reduction and resistance use the PRE-impact durability.
                    if penetrated:
                        state = ruleset.calculate_post_penetration_state(state, layer)
                    else:
                        shot_blunt += ruleset.calculate_blunt_damage(state, layer, layers[index + 1:])
                    layer.current_durability = max(0.0, layer.current_durability - loss)
                    if not penetrated:
                        break
                else:
                    penetrated_shot = True
                    shot_health += state.remaining_damage
            health_sums[shot] += shot_health
            blunt_sums[shot] += shot_blunt
            cumulative_damage += shot_health + shot_blunt
            if penetrated_shot:
                penetration_counts[shot] += 1
                if first_shot == 0:
                    first_shot = shot + 1
            if threshold is not None and cumulative_damage >= threshold:
                kill_counts[shot] += 1
            for index, layer in enumerate(layers):
                durability_sums[shot + 1][index] += layer.current_durability
        first_counts[first_shot] += 1
        if progress and (iteration + 1) % max(1, count // 100) == 0:
            progress(round((iteration + 1) / count * 100))

    health = [value / count for value in health_sums]
    blunt = [value / count for value in blunt_sums]
    result = _single(replace(scenario, shot_count=1), ruleset)
    result.final_penetration_probability = penetration_counts[0] / count
    result.expected_health_damage, result.expected_blunt_damage = health[0], blunt[0]
    result.expected_total_damage = health[0] + blunt[0]
    result.expected_burst_health_damage = sum(health)
    result.expected_burst_blunt_damage = sum(blunt)
    result.expected_burst_total_damage = sum(health) + sum(blunt)
    result.health_damage_by_shot, result.blunt_damage_by_shot = health, blunt
    result.penetration_probability_by_shot = [value / count for value in penetration_counts]
    result.kill_probability_by_shot = ([value / count for value in kill_counts]
                                       if threshold is not None else [])
    result.first_penetration_shot_distribution = {
        shot: first_counts[shot] / count for shot in range(1, shots + 1) if first_counts[shot]
    }
    result.durability_timeline = [
        DurabilitySnapshot(0, tuple(layer.current_durability for layer in templates)),
        *[DurabilitySnapshot(shot, tuple(value / count for value in durability_sums[shot]))
          for shot in range(1, shots + 1)],
    ]
    result.penetration_confidence_interval = _wilson(penetration_counts[0], count)
    result.sample_count, result.method = count, "monte-carlo-trajectories"
    return result
