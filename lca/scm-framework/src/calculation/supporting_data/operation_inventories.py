"""Database-free reference inventories for conventional unit operations.

Unit records reference 1 kg of named material. The process inventory_basis
maps that reference to processed input or recovered target output exactly once.
Screening and Sieving remain separate; Crushing follows the user's new table.
"""
from copy import deepcopy

from .version import LIBRARY_VERSION


HEAVY_MACHINE = "market for industrial machine, heavy, unspecified, RER"
ELECTRICITY = "market for electricity, medium voltage, DE"


def exchange(code, label, value, unit, activity):
    return dict(code=code, label=label, value=value, unit=unit, activity=activity)


FIXED_INVENTORIES = {
    "Crushing": {
        "id": "user-crushing-2026-09-22", "source_function": "User-confirmed inventory table, 2026-09-22",
        "exchanges": [
            exchange("diesel_burned_mj", "Diesel combustion", 5.07e-3, "MJ", "diesel, burned in building machine, GLO"),
            exchange("water_input_kg", "Tap water", 0.0007, "kg", "market for tap water, Europe without Switzerland"),
        ],
    },
    "Sieving": {
        "id": "cycle2-sieving-v1", "source_function": "Processes.get_sieving_process",
        "exchanges": [
            exchange("electricity_kwh", "Electricity", 8.22e-5, "kWh", ELECTRICITY),
            exchange("heavy_machine_kg", "Heavy machine", 5.64e-10, "kg", HEAVY_MACHINE),
        ],
    },
    "Sorting": {
        "id": "cycle2-sorting-v1", "source_function": "S1.1 Pysical, sorting inventory (including E29-E30)",
        "source_file": "SI1-3_ParameterAndInventories.xlsx",
        "exchanges": [
            exchange("electricity_kwh", "Electricity", 3.70e-3, "kWh", ELECTRICITY),
            exchange("diesel_burned_mj", "Diesel combustion", 4.37e-3, "MJ", "market for diesel, burned in building machine, GLO"),
            exchange("hydraulic_digger_m3", "Hydraulic digger", 3.53e-4, "m³", "excavation, hydraulic digger, RER"),
            exchange("sorting_facility_unit", "Sorting facility", 1.0e-10, "unit", "sorting facility construction, for construction waste, RoW"),
        ],
    },
    "Screening": {
        "id": "cycle2-screening-v1", "source_function": "Fixed screening inventory",
        "exchanges": [
            exchange("electricity_kwh", "Electricity", 8.83e-5, "kWh", ELECTRICITY),
            exchange("heavy_machine_kg", "Heavy machine", 4.17e-11, "kg", HEAVY_MACHINE),
        ],
    },
}

def fixed_inventory(name):
    record = deepcopy(FIXED_INVENTORIES[name])
    return {
        **record, "version": LIBRARY_VERSION,
        "source_file": record.get("source_file", "User-confirmed Sorting/Sieving/Crushing/Screening table, 2026-09-22"),
        "basis": "per kg reference material; inventory_basis specifies processed input or target output",
    }
