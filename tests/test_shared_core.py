import json
from pathlib import Path

import pytest
from tarkov_sim_core import (
    calculate_analytic_json,
    get_engine_metadata_json,
    simulate_json,
    validate_scenario_json,
)

VECTORS = Path(__file__).parents[1] / "shared" / "test_vectors"


@pytest.mark.parametrize("path", sorted(VECTORS.glob("*.tarkovsim.json")))
def test_shared_vectors_validate_and_calculate(path: Path) -> None:
    vector = json.loads(path.read_text(encoding="utf-8"))
    validation = json.loads(validate_scenario_json(vector["input"]))
    assert validation["valid"], validation["errors"]
    result = json.loads(calculate_analytic_json(vector["input"]))
    assert result["ok"]
    assert 0 <= result["result"]["final_penetration_probability"] <= 1
    for key, expected in vector["expected"].items():
        actual = result["result"][key]
        assert (
            actual == pytest.approx(expected) if isinstance(expected, float) else actual == expected
        )


def test_shared_monte_carlo_is_deterministic() -> None:
    vector = json.loads((VECTORS / "continuous_fire.tarkovsim.json").read_text(encoding="utf-8"))
    assert simulate_json(vector["input"]) == simulate_json(vector["input"])


def test_engine_metadata_is_versioned() -> None:
    metadata = json.loads(get_engine_metadata_json())
    assert metadata["schema_version"] == 1
    assert metadata["core_version"] == "2.1.0"
