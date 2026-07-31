from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from ..models import (
    Ammo,
    ArmorLayer,
    ArmorLayerType,
    ArmorMaterial,
    BodyPart,
    ShotScenario,
    SimulationResult,
)


def load_payload(value: str | dict[str, Any]) -> dict[str, Any]:
    return json.loads(value) if isinstance(value, str) else value


def scenario_from_dict(payload: dict[str, Any]) -> ShotScenario:
    ammo_data = dict(payload["ammo"])
    ammo_data["aliases"] = tuple(ammo_data.get("aliases", ()))
    ammo = Ammo(**ammo_data)
    layers = []
    for raw in payload["armor_layers"]:
        data = dict(raw)
        data["layer_type"] = ArmorLayerType(data["layer_type"])
        data["material"] = ArmorMaterial(data["material"])
        data["protection_zones"] = tuple(data.get("protection_zones", ("thorax",)))
        layers.append(ArmorLayer(**data))
    return ShotScenario(
        ammo=ammo,
        armor_layers=tuple(layers),
        body_part=BodyPart(payload.get("body_part", "thorax")),
        distance_m=float(payload.get("distance_m", 0)),
        shot_count=int(payload.get("shot_count", 1)),
        simulation_iterations=int(payload.get("simulation_iterations", 10_000)),
        enable_fragmentation=bool(payload.get("enable_fragmentation", False)),
        enable_distance_decay=bool(payload.get("enable_distance_decay", True)),
        enable_skills=bool(payload.get("enable_skills", False)),
        random_seed=payload.get("random_seed"),
    )


def result_to_dict(result: SimulationResult) -> dict[str, Any]:
    payload = asdict(result)
    payload["confidence"] = result.confidence.value
    payload["three_shot_penetration_probability"] = result.three_shot_penetration_probability
    payload["expected_first_penetration_shot"] = result.expected_first_penetration_shot
    payload["first_penetration_shot_distribution"] = {
        str(key): value for key, value in result.first_penetration_shot_distribution.items()
    }
    return payload


def dump_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
