from __future__ import annotations

import csv
import json
from pathlib import Path

from .models import ShotScenario, SimulationResult
from .rulesets import BallisticsRuleset


def result_summary(result: SimulationResult, shot_count: int) -> str:
    p = result.final_penetration_probability
    if p < 0.15:
        text = "首发极难击穿"
    elif p < 0.35:
        text = "首发较难击穿"
    elif p < 0.65:
        text = "首发胜负接近五五开"
    elif p < 0.85:
        text = "首发较易击穿"
    else:
        text = "首发极易击穿"
    expected = result.expected_first_penetration_shot
    if shot_count > 1 and expected is not None:
        text += f"，连续命中时预计第 {expected:.1f} 发首次穿透"
    return text + "。"


def export_json(path: Path, scenario: ShotScenario, result: SimulationResult) -> None:
    payload = {
        "ammo": scenario.ammo.short_name,
        "armor": [layer.name for layer in scenario.armor_layers],
        "distance_m": scenario.distance_m,
        "shots": scenario.shot_count,
        "first_shot_penetration": result.final_penetration_probability,
        "three_shot_penetration": result.three_shot_penetration_probability,
        "expected_health_damage": result.expected_health_damage,
        "expected_blunt_damage": result.expected_blunt_damage,
        "kill_probability_by_shot": result.kill_probability_by_shot,
        "data_version": result.data_version,
        "ruleset_version": result.ruleset_version,
        "confidence": result.confidence.value,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def export_csv(path: Path, scenario: ShotScenario, result: SimulationResult) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.writer(stream)
        writer.writerow(["弹药", "护甲", "首发穿透率", "3发内穿透率", "期望肉伤", "期望钝伤"])
        writer.writerow(
            [
                scenario.ammo.short_name,
                " → ".join(layer.name for layer in scenario.armor_layers),
                result.final_penetration_probability,
                result.three_shot_penetration_probability,
                result.expected_health_damage,
                result.expected_blunt_damage,
            ]
        )


class SimulationService:
    def __init__(self, ruleset: BallisticsRuleset) -> None:
        self.ruleset = ruleset

    def analyze(self, scenario: ShotScenario) -> SimulationResult:
        from .engine import analyze

        return analyze(scenario, self.ruleset)

