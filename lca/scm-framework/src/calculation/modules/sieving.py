from __future__ import annotations

from ..process_settings.separation import SIEVING_SPECS
from .fixed_inventory import calculate_fixed_inventory
from src.calculation.schemas import ProcessInput


def calculate_sieving(process_input: ProcessInput):
    return calculate_fixed_inventory(process_input, SIEVING_SPECS, separation=True)
