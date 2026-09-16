from __future__ import annotations

from collections.abc import Mapping

from ..serialization import scenario_from_dict


def validate_scenario_payload(payload: Mapping[str, object]) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    if not isinstance(payload, Mapping):
        return [{"path": "$", "message": "Scenario must be an object"}]
    if type(payload.get("schema_version")) is not int or payload.get("schema_version") != 1:
        errors.append({"path": "schema_version", "message": "Must be integer 1"})
    ammo = payload.get("ammo")
    if not isinstance(ammo, Mapping):
        errors.append({"path": "ammo", "message": "Must be an object"})
    else:
        for name in ("id", "name", "short_name", "caliber"):
            if not isinstance(ammo.get(name), str) or not ammo[name].strip():
                errors.append({"path": f"ammo.{name}", "message": "Must be nonempty text"})
    layers = payload.get("armor_layers")
    if not isinstance(layers, list) or len(layers) > 12:
        errors.append({"path": "armor_layers", "message": "Must be a list of 0 to 12 layers"})
    elif any(not isinstance(layer, Mapping) for layer in layers):
        errors.append({"path": "armor_layers", "message": "Each layer must be an object"})
    if payload.get("ruleset", "current") not in ("current", "experimental"):
        errors.append({"path": "ruleset", "message": "Unknown ruleset"})
    if not errors:
        try:
            scenario = scenario_from_dict(dict(payload))
            # Bound total work as well as each individual input. Mobile and desktop
            # both use this bridge; imported files must not freeze either frontend.
            work = (scenario.shot_count * scenario.ammo.projectile_count
                    * max(1, len(scenario.armor_layers)) * scenario.simulation_iterations)
            if work > 100_000_000:
                errors.append({"path": "simulation_iterations", "message": "Work budget exceeded"})
        except (ValueError, TypeError, KeyError, AttributeError, OverflowError) as exc:
            errors.append({"path": "$", "message": str(exc)})
    return errors
