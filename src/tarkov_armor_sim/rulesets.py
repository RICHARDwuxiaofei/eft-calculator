from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from .models import (
    ArmorLayer,
    CalculationConfidence,
    ProjectileState,
)


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


class CurrentApproximation:
    """Auditable approximation, deliberately not presented as the hidden game formula."""

    metadata = RulesetMetadata(
        name="当前社区近似",
        version="community-approx-2026.07-v1",
        game_version="1.0.6.0",
        created_at="2026-07-30",
        confidence=CalculationConfidence.APPROXIMATION,
        sources=(
            "https://escapefromtarkov.fandom.com/wiki/Ballistics",
            "https://tarkov.dev/api/",
            "https://changes.tarkov-changes.com/",
        ),
        limitations=(
            "官方未公开完整穿透随机函数",
            "穿透后伤害/穿深衰减为可替换近似",
            "钝伤、碎裂和距离衰减为近似",
        ),
        default_allowed=True,
    )

    def penetration_probability(
        self, projectile: ProjectileState, armor: ArmorLayer
    ) -> float:
        ratio = armor.true_durability_ratio
        effective_class = armor.armor_class * (0.55 + 0.45 * ratio)
        margin = projectile.remaining_penetration - effective_class * 10.0
        # Smooth, monotonic approximation with useful end caps.
        probability = 1.0 / (1.0 + 2.718281828 ** (-margin / 4.5))
        return min(0.99, max(0.01, probability))

    def calculate_armor_damage(
        self, projectile: ProjectileState, armor: ArmorLayer, penetrated: bool
    ) -> float:
        energy_factor = max(0.35, projectile.remaining_penetration / (armor.armor_class * 10))
        stopped_factor = 1.15 if not penetrated else 0.75
        return max(
            0.1,
            projectile.remaining_penetration
            * 0.1
            * armor.destructibility
            * energy_factor
            * stopped_factor,
        )

    def calculate_post_penetration_state(
        self, projectile: ProjectileState, armor: ArmorLayer
    ) -> ProjectileState:
        ratio = armor.true_durability_ratio
        loss = min(0.42, 0.10 + armor.armor_class * 0.025 + ratio * 0.05)
        return ProjectileState(
            remaining_damage=max(0.0, projectile.remaining_damage * (1.0 - loss)),
            remaining_penetration=max(
                0.0, projectile.remaining_penetration - armor.armor_class * (2.8 + ratio)
            ),
            current_layer_index=projectile.current_layer_index + 1,
            stopped=False,
        )

    def calculate_blunt_damage(
        self,
        projectile: ProjectileState,
        stopped_by: ArmorLayer,
        backing_layers: Sequence[ArmorLayer],
    ) -> float:
        backing_reduction = max(0.55, 1.0 - len(backing_layers) * 0.08)
        return projectile.remaining_damage * stopped_by.blunt_throughput * backing_reduction


class ExperimentalRuleset(CurrentApproximation):
    metadata = RulesetMetadata(
        name="实验性距离强化",
        version="experimental-distance-2026.07-v1",
        game_version="1.0.6.0",
        created_at="2026-07-30",
        confidence=CalculationConfidence.EXPERIMENTAL,
        sources=CurrentApproximation.metadata.sources,
        limitations=CurrentApproximation.metadata.limitations
        + ("距离衰减被有意放大，仅用于敏感性分析",),
        default_allowed=False,
    )
