from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


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
        if not 1 <= self.armor_class <= 6:
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

    @property
    def three_shot_penetration_probability(self) -> float:
        chance_none = 1.0
        for value in self.penetration_probability_by_shot[:3]:
            chance_none *= 1.0 - value
        return 1.0 - chance_none

    @property
    def expected_first_penetration_shot(self) -> float | None:
        total = sum(self.first_penetration_shot_distribution.values())
        if total <= 0:
            return None
        return sum(k * v for k, v in self.first_penetration_shot_distribution.items()) / total
