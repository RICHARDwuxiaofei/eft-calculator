"""Portable simulation core shared by the Windows and Android applications."""

from .api import (
    calculate_analytic_json,
    compare_json,
    get_engine_metadata_json,
    simulate_json,
    validate_scenario_json,
)

__all__ = [
    "calculate_analytic_json",
    "compare_json",
    "get_engine_metadata_json",
    "simulate_json",
    "validate_scenario_json",
]

SCHEMA_VERSION = 1
CORE_VERSION = "2.1.0"
