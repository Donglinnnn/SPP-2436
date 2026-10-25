"""Assemble reference choices and input defaults for the API catalogue.

Reference values live in supporting_data, input defaults in process_settings,
and derived calibration values are calculated by their model.
"""
from dataclasses import MISSING, fields

from .models.grinding import grinding_library
from .process_settings.thermal_activation import StandardizedScenario, ThermalActivationSettings
from .supporting_data.operation_inventories import FIXED_INVENTORIES, fixed_inventory
from .supporting_data.thermal_reactions import thermal_reaction_library
from .supporting_data.version import LIBRARY_VERSION


def input_libraries():
    thermal_defaults = {
        "settings": {field.name: field.default for field in fields(ThermalActivationSettings)
                     if field.default is not MISSING},
        "scenario": {field.name: field.default for field in fields(StandardizedScenario)
                     if field.default is not MISSING},
    }
    return {
        "version": LIBRARY_VERSION,
        "fixed_inventory": {name: fixed_inventory(name) for name in FIXED_INVENTORIES},
        "grinding": grinding_library(),
        "thermal_reactions": thermal_reaction_library(),
        "thermal_defaults": thermal_defaults,
    }
