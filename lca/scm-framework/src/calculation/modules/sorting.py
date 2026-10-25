from __future__ import annotations

from ..process_settings.separation import SORTING_SPECS
from .fixed_inventory import calculate_fixed_inventory
from src.calculation.schemas import ProcessInput


def calculate_sorting(process_input: ProcessInput):
    return calculate_fixed_inventory(process_input, SORTING_SPECS, separation=True)
