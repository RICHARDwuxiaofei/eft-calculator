"""Independent Decimal event tree for the documented COMMUNITY model, not game ground truth.

Reference calculations do not import the production rules, engine or helpers. The
runner imports the public bridge only after constructing all expected outcomes.
"""
from __future__ import annotations

import json
from decimal import Decimal, localcontext
from pathlib import Path

D = Decimal
ROOT = Path(__file__).resolve().parents[1]
COEFFICIENTS = {"aramid": "0.1875", "uhmwpe": "0.3375", "combined": "0.375",
                "titanium": "0.4125", "aluminum": "0.45", "steel": "0.525",
                "ceramic": "0.6", "glass": "0.6"}


def decimal(value):
    return D(str(value))


def bounded(value, low, high):
    return max(decimal(low), min(decimal(high), value))


def interaction(damage, pen, durability, layer, armor_damage):
    if durability == 0:
        return D(1), D(0), D(0), damage, pen, D(0)
    resistance = (D(121) - D(5000)/(D(45)+D(200)*durability/decimal(layer["original_max_durability"]))) * decimal(layer["armor_class"])/D(10)
    if pen <= 0 or pen <= resistance-D(15):
        probability = D(0)
    elif pen >= resistance+D(15):
        probability = D(1)
    elif pen < resistance:
        probability = D("0.004") * (resistance-pen-D(15))**2
    else:
        probability = (D(100)+pen/(D("0.9")*resistance-pen))/D(100)
    probability = bounded(probability, 0, 1)
    relative = pen/(decimal(layer["armor_class"])*D(10))
    base = pen*armor_damage/D(100)*decimal(layer["destructibility"])
    wear_pass = min(durability, max(D(1), base*bounded(relative, ".5", ".9")))
    wear_stop = min(durability, max(D(1), base*bounded(relative, ".6", "1.1")))
    attenuation = bounded(pen/(resistance+D(12)), ".6", 1)
    blunt = damage*decimal(layer["blunt_throughput"])*bounded(D(1)-D(".03")*(resistance-pen), ".2", 1)
    if layer["layer_type"] == "plate":
        blunt *= D(".6")
    return probability, wear_pass, wear_stop, damage*attenuation, pen*attenuation, blunt


def evaluate(payload):
    with localcontext() as context:
        context.prec = 50
        layers = [layer for layer in payload["armor_layers"] if layer.get("enabled", True)]
        ammo = payload["ammo"]
        initial_damage, initial_pen = decimal(ammo["damage"]), decimal(ammo["penetration_power"])
        if payload.get("enable_distance_decay", False):
            slope = D(".0009") if payload.get("ruleset") == "experimental" else D(".00055")
            scale = max(D(".58"), D(1)-slope*decimal(payload.get("distance_m", 0)))
            initial_damage *= scale
            initial_pen *= scale
        armor_damage = decimal(ammo["armor_damage_percent"])
        shots, pellets = payload.get("shot_count", 1), ammo.get("projectile_count", 1)
        hp = {"head": D(35), "thorax": D(85)}.get(payload.get("body_part", "thorax"))
        states = [(D(1), tuple(decimal(x["current_durability"]) for x in layers), D(0), 0)]
        health, blunt, penetration, killed = [], [], [], []
        first = [D(0)] * shots

        def projectile(index, durabilities, damage, pen, weight):
            if index == len(layers):
                return [(weight, durabilities, damage, D(0), True)]
            p, passing, stopping, new_damage, new_pen, b = interaction(damage, pen, durabilities[index], layers[index], armor_damage)
            branches = []
            if p < 1:
                updated = list(durabilities)
                updated[index] -= stopping
                branches.append((weight*(1-p), tuple(updated), D(0), b, False))
            if p > 0:
                updated = list(durabilities)
                updated[index] -= passing
                branches.extend(projectile(index+1, tuple(updated), new_damage, new_pen, weight*p))
            return branches

        for shot in range(shots):
            shell = [(w, ds, total, f, D(0), D(0), False) for w, ds, total, f in states]
            for _ in range(pellets):
                next_shell = []
                for weight, durabilities, total, first_shot, flesh, trauma, penetrated in shell:
                    for w, ds, h, b, hit in projectile(0, durabilities, initial_damage, initial_pen, weight):
                        next_shell.append((w, ds, total, first_shot, flesh+h, trauma+b, penetrated or hit))
                shell = next_shell
            health.append(sum((w*h for w, _, _, _, h, _, _ in shell), D(0)))
            blunt.append(sum((w*b for w, _, _, _, _, b, _ in shell), D(0)))
            penetration.append(sum((w for w, _, _, _, _, _, hit in shell if hit), D(0)))
            killed.append(sum((w for w, _, total, _, h, b, _ in shell if hp is not None and total+h+b >= hp), D(0)))
            states = []
            for w, ds, total, f, h, b, hit in shell:
                if not f and hit:
                    f = shot+1
                    first[shot] += w
                states.append((w, ds, total+h+b, f))
        return {"final_penetration_probability": float(penetration[0]),
                "expected_health_damage": float(health[0]), "expected_blunt_damage": float(blunt[0]),
                "expected_burst_total_damage": float(sum(health)+sum(blunt)),
                "penetration_probability_by_shot": list(map(float, penetration)),
                "first_penetration_shot_distribution": {str(i+1): float(v) for i, v in enumerate(first)},
                "kill_probability_by_shot": list(map(float, killed)) if hp else []}


def scenario(level=5, ratio=1, pen=40, material="ceramic", damage=50, pellets=1, shots=1):
    return {"schema_version": 1,
            "ammo": {"id": "independent", "name": "Independent reference", "short_name": "REF", "caliber": "reference",
                     "damage": damage, "penetration_power": pen, "armor_damage_percent": 50, "projectile_count": pellets},
            "armor_layers": [{"id": "reference", "name": "Reference layer", "layer_type": "plate", "armor_class": level,
                              "current_durability": 100*ratio, "displayed_max_durability": 100,
                              "original_max_durability": 100, "material": material,
                              "destructibility": float(COEFFICIENTS[material]), "blunt_throughput": .1, "is_hard_armor": True}],
            "body_part": "thorax", "distance_m": 0, "enable_distance_decay": False,
            "shot_count": shots, "simulation_iterations": 100000, "random_seed": 20261025}


def cases():
    result = []
    for level in range(1, 7):
        for ratio in (0, .25, .5, 1):
            for offset in (-12, 0, 16):
                result.append((f"class-{level}-durability-{ratio}-offset-{offset}", scenario(level, ratio, max(0, level*10+offset))))
    for material in COEFFICIENTS:
        result.append((f"material-{material}", scenario(material=material)))
    for name, damage, pen in (("DBX95",57,33),("DBP191",53,39),("DVX12",48,47),("DVC12",46,52)):
        p = scenario(pen=pen, damage=damage)
        p["ammo"].update(name=name, short_name=name, caliber="5.8x42")
        result.append((name, p))
    p = scenario(ratio=.5)
    p["armor_layers"][0]["displayed_max_durability"] = 50
    result.append(("repaired-50-of-original-100", p))
    p = scenario(pen=0, pellets=8)
    p["armor_layers"][0]["current_durability"] = 4
    result.append(("eight-pellets-break-after-four", p))
    p = scenario(pen=0, shots=3)
    p["armor_layers"][0]["current_durability"] = 2
    result.append(("three-triggers-break-after-two", p))
    p = scenario(pen=52, shots=3)
    p["armor_layers"].append(scenario(level=3, material="aramid")["armor_layers"][0])
    p["armor_layers"][1]["layer_type"] = "soft"
    result.append(("three-triggers-two-layers", p))
    for body in ("head", "stomach"):
        p = scenario(pen=52, shots=3)
        p["body_part"] = body
        result.append((f"{body}-health", p))
    for enabled in (False, True):
        p = scenario(pen=44)
        p.update(distance_m=250, enable_distance_decay=enabled)
        result.append((f"distance-enabled-{enabled}", p))
    return [{"id": name, "input": payload, "expected": evaluate(payload),
             "basis": "independent 50-digit Decimal event enumeration of documented community equations; NOT in-game measurements"}
            for name, payload in result]


def main():
    rows = cases()
    destination = ROOT / "tests/fixtures/independent_cases_2026_10_25.json"
    destination.write_text(json.dumps(rows, indent=2)+"\n", encoding="utf-8")
    print(f"Wrote {len(rows)} independent cases", flush=True)
    from tarkov_sim_core.api import calculate_analytic_json, simulate_json

    observations = []
    for row in rows:
        value = row["input"]
        exact = value["shot_count"] == value["ammo"]["projectile_count"] == 1
        # 100k samples for dependent histories; analytic tests use exact comparisons.
        actual = json.loads((calculate_analytic_json if exact else simulate_json)(value))["result"]
        errors = {key: actual[key]-row["expected"][key] for key in (
            "final_penetration_probability", "expected_health_damage", "expected_blunt_damage", "expected_burst_total_damage")}
        observations.append({"id": row["id"], "method": actual["method"], "samples": actual["sample_count"],
                             "errors": errors, "probability_interval_95": actual["penetration_confidence_interval"],
                             "expected_probability": row["expected"]["final_penetration_probability"]})
    report = ROOT / "artifacts/audit-2026-10-25/numerical.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(observations, indent=2)+"\n", encoding="utf-8")
    print(f"Compared {len(rows)} cases; max exact probability error=" + str(max(abs(x["errors"]["final_penetration_probability"]) for x in observations if not x["samples"])))


if __name__ == "__main__":
    main()
