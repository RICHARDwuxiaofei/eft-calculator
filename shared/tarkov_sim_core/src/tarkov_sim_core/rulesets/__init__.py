from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from ..models import ArmorLayer, CalculationConfidence, ProjectileState


@dataclass(frozen=True)
class RulesetMetadata:
    name: str
    version: str
    game_version: str
    created_at: str
    confidence: CalculationConfidence
    sources: tuple[str, ...]
    limitations: tuple[str, ...]
    default_allowed: bool


class BallisticsRuleset(Protocol):
    metadata: RulesetMetadata

    def penetration_probability(
        self, projectile: ProjectileState, armor: ArmorLayer
    ) -> float: ...

    def calculate_armor_damage(
        self, projectile: ProjectileState, armor: ArmorLayer, penetrated: bool
    ) -> float: ...

    def calculate_post_penetration_state(
        self, projectile: ProjectileState, armor: ArmorLayer
    ) -> ProjectileState: ...

    def calculate_blunt_damage(
        self,
        projectile: ProjectileState,
        stopped_by: ArmorLayer,
        backing_layers: Sequence[ArmorLayer],
    ) -> float: ...


# Wiki material coefficients. A live item may override this with sourced data.
MATERIAL_DESTRUCTIBILITY = {
    "aramid": 0.1875, "uhmwpe": 0.3375, "combined": 0.375,
    "titanium": 0.4125, "aluminum": 0.45, "steel": 0.525,
    "ceramic": 0.6, "glass": 0.6,
}


def clamp(value: float, low: float, high: float) -> float:
    return min(high, max(low, value))


def armor_resistance(armor: ArmorLayer) -> float:
    """Community durability curve; current/original, NEVER current/repaired maximum.

    Reference: https://www.desmos.com/calculator/m8cmsfokkl
    The published modern curve uses TWO times durability percentage.
    See docs/RESEARCH.md for version/verification limits.
    """
    if armor.current_durability <= 0:
        return 0.0
    return (121.0 - 5000.0 / (45.0 + 200.0 * armor.true_durability_ratio)) * (
        armor.armor_class * 0.1
    )


class CurrentApproximation:
    """Sourced community model, not a claim of access to current server code."""

    metadata = RulesetMetadata(
        name="Community reference / current-original durability",
        version="community-reference-2026.09-v3",
        game_version="unverified-current-patch",
        created_at="2026-09-18",
        confidence=CalculationConfidence.APPROXIMATION,
        sources=(
            "https://escapefromtarkov.fandom.com/wiki/Ballistics",
            "https://escapefromtarkov.fandom.com/wiki/Changelog#0.14.6.0.29862",
            "https://www.desmos.com/calculator/m8cmsfokkl",
            ("https://github.com/bugybon/TarkovBallisticsSimulator/blob/"
             "82ea32437423c2f1d3ed9ad5d2807eaba15efbc4/api/balistics.js"),
            "https://tarkov.dev/api/",
        ),
        limitations=(
            "Current server formula is not independently confirmed by in-game measurements",
            "Armor damage, post-penetration loss and blunt damage are community models",
            "One chosen hit path; no ricochet, hitbox miss, fragmentation or black-limb overflow",
            "Nonzero-distance linear decay is experimental, not a validated flight model",
        ),
        default_allowed=True,
    )

    def penetration_probability(self, projectile: ProjectileState, armor: ArmorLayer) -> float:
        if armor.current_durability <= 0:
            return 1.0
        pen = projectile.remaining_penetration
        if pen <= 0:
            return 0.0
        resistance = armor_resistance(armor)
        # BSG's 0.14.6 armor penetration rework explicitly documents a guaranteed
        # penetration when penetration power is at least 15 above effective armor
        # durability. Keep that hard boundary instead of letting the smooth community
        # curve asymptotically stop below 100% in this region.
        if pen >= resistance + 15.0:
            return 1.0
        if pen >= resistance:
            probability = (100.0 + pen / (0.9 * resistance - pen)) / 100.0
        elif pen > resistance - 15.0:
            probability = 0.004 * (resistance - pen - 15.0) ** 2
        else:
            probability = 0.0
        return clamp(probability, 0.0, 1.0)

    def calculate_armor_damage(
        self, projectile: ProjectileState, armor: ArmorLayer, penetrated: bool
    ) -> float:
        if armor.current_durability <= 0:
            return 0.0
        # Divide by (class * 10), not divide by class then multiply by ten.
        # Do not copy the reference JS's max(x, lower, upper) typo.
        relative_pen = projectile.remaining_penetration / (armor.armor_class * 10.0)
        factor = clamp(relative_pen, 0.5, 0.9) if penetrated else clamp(relative_pen, 0.6, 1.1)
        damage = (projectile.remaining_penetration * projectile.armor_damage_percent / 100.0
                  * factor * armor.destructibility)
        return min(armor.current_durability, max(1.0, damage))

    def calculate_post_penetration_state(
        self, projectile: ProjectileState, armor: ArmorLayer
    ) -> ProjectileState:
        factor = (1.0 if armor.current_durability <= 0 else
                  clamp(projectile.remaining_penetration / (armor_resistance(armor) + 12.0),
                        0.6, 1.0))
        return ProjectileState(
            remaining_damage=projectile.remaining_damage * factor,
            remaining_penetration=projectile.remaining_penetration * factor,
            current_layer_index=projectile.current_layer_index + 1,
            armor_damage_percent=projectile.armor_damage_percent,
        )

    def calculate_blunt_damage(
        self, projectile: ProjectileState, stopped_by: ArmorLayer,
        backing_layers: Sequence[ArmorLayer],
    ) -> float:
        if stopped_by.current_durability <= 0:
            return 0.0
        factor = clamp(1.0 - 0.03 * (armor_resistance(stopped_by)
                                    - projectile.remaining_penetration), 0.2, 1.0)
        # No arbitrary reduction by number of backing layers. The model does not
        # claim to resolve compression/impulse propagation through multilayer armor.
        plate_factor = 0.6 if stopped_by.layer_type.value == "plate" else 1.0
        return projectile.remaining_damage * stopped_by.blunt_throughput * factor * plate_factor


class ExperimentalRuleset(CurrentApproximation):
    metadata = RulesetMetadata(
        name="Experimental distance sensitivity",
        version="experimental-distance-2026.09-v3",
        game_version="unverified-current-patch",
        created_at="2026-09-18",
        confidence=CalculationConfidence.EXPERIMENTAL,
        sources=CurrentApproximation.metadata.sources,
        limitations=CurrentApproximation.metadata.limitations,
        default_allowed=False,
    )
