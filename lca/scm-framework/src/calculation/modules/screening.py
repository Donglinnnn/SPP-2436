from ..process_settings.separation import SCREENING_SPECS
from .fixed_inventory import calculate_fixed_inventory


def calculate_screening(process_input):
    return calculate_fixed_inventory(process_input, SCREENING_SPECS, separation=True)
