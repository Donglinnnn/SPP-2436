"""Thermal-activation defaults shared by the web schema and Python model.

Engineering assumptions preserve the current web calculation. Material-property
defaults reference supporting_data; activation temperature and holding time are
route inputs and deliberately have no defaults here.
"""
from types import MappingProxyType

from ..supporting_data.infrastructure import THERMAL_FACTORY_UNIT_PER_KG_PRODUCT_H
from ..supporting_data.material_properties import (
    CP_CO2_KJ_PER_KG_K,
    CP_H2O_STEAM_KJ_PER_KG_K,
    CP_LIQUID_WATER_KJ_PER_KG_K,
    CP_SOLID_DEFAULT_KJ_PER_KG_K,
    LATENT_HEAT_H2O_KJ_PER_KG,
)


FREE_WATER_EVAPORATION_CUTOFF_C = 105.0

SETTINGS_DEFAULTS = MappingProxyType({
    "ambient_temperature_C": 25.0,
    "cp_feed_kj_per_kg_k": CP_SOLID_DEFAULT_KJ_PER_KG_K,
    "cp_h2o_steam_kj_per_kg_k": CP_H2O_STEAM_KJ_PER_KG_K,
    "cp_co2_kj_per_kg_k": CP_CO2_KJ_PER_KG_K,
    "cp_liquid_water_kj_per_kg_k": CP_LIQUID_WATER_KJ_PER_KG_K,
    "latent_heat_h2o_kj_per_kg": LATENT_HEAT_H2O_KJ_PER_KG,
    "free_water_evaporation_cutoff_C": FREE_WATER_EVAPORATION_CUTOFF_C,
    "thermal_factory_unit_per_kg_product_h": THERMAL_FACTORY_UNIT_PER_KG_PRODUCT_H,
})

SCENARIO_DEFAULTS = MappingProxyType({
    "name": "base_case",
    "lambda_heatup": 1.15,
    "hold_loss_kj_per_kg_h_per_deltaT100K": 22.0,
    "gas_exit_temperature_C": None,  # Resolved to the supplied activation temperature.
})
