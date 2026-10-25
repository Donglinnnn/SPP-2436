"""Foreground-flow classification and background-provider mapping rules.

Multipliers convert foreground quantities to the selected provider's unit.
The wastewater factor retains the existing 1,000 kg/m³ density assumption.
These rules belong to LCIA linking, not to material reference data.
"""
from src.calculation.units import KWH_TO_MJ


FLOW_MAP = {
    'electricity_kwh': ('electricity', 1), 'heat_kwh': ('heat', KWH_TO_MJ),
    'water_input_kg': ('water', 1), 'wastewater_treatment_kg': ('wastewater', .001),
    'diesel_burned_mj': ('diesel', 1), 'heavy_machine_kg': ('machine', 1),
    'grinding_machine_kg': ('machine', 1), 'hydraulic_digger_m3': ('digger', 1),
    'sorting_facility_unit': ('sorting', 1),
    'thermal_factory_unit': ('thermal_factory', 1),
    'carbonation_factory_unit': ('carbonation_factory', 1),
}

# Retained in physical balances without a second independent GWP contribution.
# CO2 make-up losses are characterized through the co2_emitted_kg alias.
PHYSICAL_ONLY = {'solid_loss_kg', 'coproduct_kg', 'water_to_air_kg', 'water_evaporated_kg',
                 'water_in_product_kg', 'wastewater_release_kg', 'co2_makeup_loss_kg'}
