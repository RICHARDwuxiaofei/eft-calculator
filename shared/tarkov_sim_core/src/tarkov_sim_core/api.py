from __future__ import annotations

from typing import Any

from .engine import analyze, simulate
from .rulesets import CurrentApproximation, ExperimentalRuleset
from .serialization import dump_json, load_payload, result_to_dict, scenario_from_dict
from .validation import validate_scenario_payload

SCHEMA_VERSION = 1
CORE_VERSION = "2.1.1"


def _ruleset(payload: dict[str, Any]):
    return (
        ExperimentalRuleset()
        if payload.get("ruleset") == "experimental"
        else CurrentApproximation()
    )


def get_engine_metadata_json() -> str:
    rules = CurrentApproximation.metadata
    return dump_json(
        {
            "schema_version": SCHEMA_VERSION,
            "core_version": CORE_VERSION,
            "ruleset": {
                "name": rules.name,
                "version": rules.version,
                "game_version": rules.game_version,
                "confidence": rules.confidence.value,
                "limitations": list(rules.limitations),
            },
        }
    )


def validate_scenario_json(value: str | dict[str, Any]) -> str:
    try:
        payload = load_payload(value)
        errors = validate_scenario_payload(payload)
    except (TypeError, ValueError, KeyError) as exc:
        errors = [{"path": "$", "message": str(exc)}]
    return dump_json({"schema_version": SCHEMA_VERSION, "valid": not errors, "errors": errors})


def _calculate(value: str | dict[str, Any], *, monte_carlo: bool) -> str:
    payload = load_payload(value)
    errors = validate_scenario_payload(payload)
    if errors:
        return dump_json({"schema_version": SCHEMA_VERSION, "ok": False, "errors": errors})
    scenario = scenario_from_dict(payload)
    result = (
        simulate(scenario, _ruleset(payload))
        if monte_carlo
        else analyze(scenario, _ruleset(payload))
    )
    return dump_json(
        {"schema_version": SCHEMA_VERSION, "ok": True, "result": result_to_dict(result)}
    )


def calculate_analytic_json(value: str | dict[str, Any]) -> str:
    return _calculate(value, monte_carlo=False)


def simulate_json(value: str | dict[str, Any]) -> str:
    return _calculate(value, monte_carlo=True)


def compare_json(value: str | dict[str, Any]) -> str:
    payload = load_payload(value)
    scenarios = payload.get("scenarios", [])
    results = [load_payload(calculate_analytic_json(item)) for item in scenarios]
    return dump_json(
        {"schema_version": SCHEMA_VERSION, "ok": all(x.get("ok") for x in results), "items": results}
    )
