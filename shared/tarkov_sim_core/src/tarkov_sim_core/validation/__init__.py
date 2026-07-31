from __future__ import annotations

from collections.abc import Mapping


def validate_scenario_payload(payload: Mapping[str, object]) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    if payload.get("schema_version") != 1:
        errors.append({"path": "schema_version", "message": "必须为 1"})
    ammo = payload.get("ammo")
    if not isinstance(ammo, Mapping):
        errors.append({"path": "ammo", "message": "必须是对象"})
    else:
        for field in ("id", "name", "short_name", "caliber"):
            if not ammo.get(field):
                errors.append({"path": f"ammo.{field}", "message": "不能为空"})
        for field in ("damage", "penetration_power", "armor_damage_percent"):
            if not isinstance(ammo.get(field), (int, float)):
                errors.append({"path": f"ammo.{field}", "message": "必须是数字"})
    layers = payload.get("armor_layers")
    if not isinstance(layers, list) or not layers:
        errors.append({"path": "armor_layers", "message": "至少需要一层护甲"})
    elif len(layers) > 12:
        errors.append({"path": "armor_layers", "message": "最多 12 层"})
    shots = payload.get("shot_count", 1)
    if not isinstance(shots, int) or not 1 <= shots <= 100:
        errors.append({"path": "shot_count", "message": "必须是 1 到 100 的整数"})
    return errors
