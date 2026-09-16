from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import isfinite


class StringEnum(str, Enum):
    def __str__(self) -> str:
        return self.value


class ArmorLayerType(StringEnum):
    PLATE = "plate"
    SOFT = "soft"
    HELMET = "helmet"


class ArmorMaterial(StringEnum):
    ARAMID = "aramid"
    UHMWPE = "uhmwpe"
    STEEL = "steel"
    TITANIUM = "titanium"
    ALUMINUM = "aluminum"
    CERAMIC = "ceramic"
    GLASS = "glass"
    COMBINED = "combined"
    UNKNOWN = "unknown"


class BodyPart(StringEnum):
    THORAX = "thorax"
    HEAD = "head"
    STOMACH = "stomach"


class CalculationConfidence(StringEnum):
    VERIFIED = "已验证"
    APPROXIMATION = "社区近似"
    EXPERIMENTAL = "实验性"


@dataclass(frozen=True)
class Ammo:
    id: str
    name: str
    short_name: str
    caliber: str
    damage: float
    penetration_power: float
    armor_damage_percent: float
    projectile_count: int = 1
    muzzle_velocity: float | None = None
    ballistic_coefficient: float | None = None
    fragmentation_chance: float | None = None
    ricochet_chance: float | None = None
    source_version: str = "bundled-snapshot-2026-07-31"
    aliases: tuple[str, ...] = ()
    localized_names: dict[str, str] = field(default_factory=dict)
    image_url: str | None = None
    wiki_url: str | None = None

    def __post_init__(self) -> None:
        for name in ("damage", "penetration_power", "armor_damage_percent"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
                raise ValueError(f"{name} must be a finite number")
        if type(self.projectile_count) is not int or not 1 <= self.projectile_count <= 64:
            raise ValueError("projectile_count must be an integer from 1 to 64")
        for name in ("muzzle_velocity", "ballistic_coefficient"):
            value = getattr(self, name)
            if value is not None and (not isfinite(value) or value <= 0):
                raise ValueError(f"{name} must be finite and positive")
        for name in ("fragmentation_chance", "ricochet_chance"):
            value = getattr(self, name)
            if value is not None and (not isfinite(value) or not 0 <= value <= 1):
                raise ValueError(f"{name} must be between 0 and 1")
        if self.damage < 0 or self.penetration_power < 0:
            raise ValueError("弹药伤害和穿深不能为负数")
        if not 0 <= self.armor_damage_percent <= 100:
            raise ValueError("甲伤百分比必须在 0 到 100 之间")
        if self.projectile_count < 1:
            raise ValueError("弹丸数量必须为正整数")

    def display_name(self, locale: str = "en_US") -> str:
        language = "zh" if locale.lower().startswith("zh") else "en"
        return self.localized_names.get(language) or self.localized_names.get("en") or self.name


@dataclass
class ArmorLayer:
    id: str
    name: str
    layer_type: ArmorLayerType
    armor_class: int
    current_durability: float
    displayed_max_durability: float
    original_max_durability: float
    material: ArmorMaterial
    destructibility: float
    blunt_throughput: float
    is_hard_armor: bool
    protection_zones: tuple[str, ...] = ("thorax",)
    enabled: bool = True

    def __post_init__(self) -> None:
        for name in ("current_durability", "displayed_max_durability",
                     "original_max_durability", "destructibility", "blunt_throughput"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
                raise ValueError(f"{name} must be a finite number")
        if type(self.armor_class) is not int or not 1 <= self.armor_class <= 6:
            raise ValueError("护甲等级必须在 1 到 6 之间")
        if self.original_max_durability <= 0:
            raise ValueError("出厂耐久必须大于 0")
        if not 0 < self.displayed_max_durability <= self.original_max_durability:
            raise ValueError("维修上限必须大于 0 且不能超过出厂耐久")
        if not 0 <= self.current_durability <= self.displayed_max_durability:
            raise ValueError("当前耐久必须在 0 与维修上限之间")
        if self.destructibility <= 0:
            raise ValueError("材料破坏系数必须大于 0")
        if not 0 <= self.blunt_throughput <= 1:
            raise ValueError("钝伤透过率必须在 0 到 1 之间")

    @property
    def true_durability_ratio(self) -> float:
        return self.current_durability / self.original_max_durability

    def clone(self) -> ArmorLayer:
        return ArmorLayer(**self.__dict__)


@dataclass(frozen=True)
class ShotScenario:
    ammo: Ammo
    armor_layers: tuple[ArmorLayer, ...]
    body_part: BodyPart = BodyPart.THORAX
    distance_m: float = 0
    shot_count: int = 1
    simulation_iterations: int = 10_000
    enable_fragmentation: bool = False
    enable_distance_decay: bool = True
    enable_skills: bool = False
    random_seed: int | None = None

    def __post_init__(self) -> None:
        if isinstance(self.distance_m, bool) or not isfinite(self.distance_m):
            raise ValueError("distance_m must be finite")
        if type(self.shot_count) is not int or type(self.simulation_iterations) is not int:
            raise ValueError("shots and iterations must be integers")
        if self.simulation_iterations > 1_000_000:
            raise ValueError("simulation_iterations must not exceed 1000000")
        if self.random_seed is not None and type(self.random_seed) is not int:
            raise ValueError("random_seed must be an integer or null")
        for name in ("enable_fragmentation", "enable_distance_decay", "enable_skills"):
            if type(getattr(self, name)) is not bool:
                raise ValueError(f"{name} must be boolean")
        if self.enable_fragmentation or self.enable_skills:
            raise ValueError("Fragmentation and skills are not implemented; disable these flags")
        if self.distance_m < 0:
            raise ValueError("距离不能为负数")
        if not 1 <= self.shot_count <= 100:
            raise ValueError("射击数必须在 1 到 100 之间")
        if self.simulation_iterations < 1:
            raise ValueError("模拟次数必须为正整数")
        if len(self.armor_layers) > 12:
            raise ValueError("护甲层数最多为 12")


@dataclass
class ProjectileState:
    remaining_damage: float
    remaining_penetration: float
    current_layer_index: int = 0
    stopped: bool = False
    armor_damage_percent: float = 0.0


@dataclass(frozen=True)
class LayerResult:
    name: str
    conditional_penetration_probability: float
    cumulative_penetration_probability: float
    stop_probability: float
    expected_durability_loss: float
    expected_durability_after: float
    remaining_damage: float
    remaining_penetration: float


@dataclass(frozen=True)
class DurabilitySnapshot:
    shot: int
    durability: tuple[float, ...]


@dataclass
class SimulationResult:
    final_penetration_probability: float
    expected_health_damage: float
    expected_blunt_damage: float
    expected_total_damage: float
    layer_results: list[LayerResult]
    durability_timeline: list[DurabilitySnapshot]
    first_penetration_shot_distribution: dict[int, float]
    kill_probability_by_shot: list[float]
    penetration_probability_by_shot: list[float] = field(default_factory=list)
    confidence: CalculationConfidence = CalculationConfidence.APPROXIMATION
    data_version: str = "bundled-snapshot-2026-07-31"
    ruleset_version: str = "community-approx-2026.07-v1"

    expected_burst_health_damage: float = 0.0
    expected_burst_blunt_damage: float = 0.0
    expected_burst_total_damage: float = 0.0
    health_damage_by_shot: list[float] = field(default_factory=list)
    blunt_damage_by_shot: list[float] = field(default_factory=list)
    penetration_confidence_interval: tuple[float, float] = (0.0, 1.0)
    sample_count: int = 0
    method: str = "exact-single-projectile"
    warnings: list[str] = field(default_factory=list)
    kill_estimate_supported: bool = True
    # Layer table always describes the first projectile, not an entire shotgun shell.
    layer_result_scope: str = "first-projectile"

    @property
    def conditional_penetrating_damage(self) -> float | None:
        """First-trigger flesh damage given at least one fully penetrating pellet."""
        if self.final_penetration_probability <= 0:
            return None
        return self.expected_health_damage / self.final_penetration_probability

    @property
    def three_shot_penetration_probability(self) -> float:
        # First-hit events are mutually exclusive; per-shot marginals are correlated.
        return min(1.0, sum(p for shot, p in self.first_penetration_shot_distribution.items()
                            if 1 <= shot <= 3))

    @property
    def expected_first_penetration_shot(self) -> float | None:
        total = sum(self.first_penetration_shot_distribution.values())
        if total <= 0:
            return None
        return sum(k * v for k, v in self.first_penetration_shot_distribution.items()) / total
