from __future__ import annotations

from typing import Any

from src.calculation import run_calculation


def calculate_project(payload: dict[str, Any]) -> dict[str, Any]:
    """Run calculation and return normalized dict payload for API responses."""
    result = run_calculation(payload)
    return result.to_dict()
