"""Carbonation engineering defaults shared by the web schema and Python model.

Values and numeric types follow the existing web calculation. Route-specific
values are selected by the operating-conditions adapter: wet fill is never
applied to dry loading; recycle and cake moisture require solid/liquid separation.
Reaction time, active heating temperature and nonzero water ratios are supplied
inputs, not implicit engineering defaults.
"""
from types import MappingProxyType

from ..supporting_data.equipment import (
    PICCINNO_GAS_EFFICIENCY,
    PICCINNO_IMPELLER_DIAMETER_M,
    PICCINNO_IMPELLER_SPEED_PER_S,
    PICCINNO_MIXING_POWER_NUMBER,
    PICCINNO_REACTOR_VOLUME_M3,
    PICCINNO_STIRRING_EFFICIENCY,
    PICCINNO_TANK_DIAMETER_M,
)
from ..supporting_data.material_properties import (
    CP_LIQUID_WATER_KJ_PER_KG_K,
    CP_SOLID_DEFAULT_KJ_PER_KG_K,
    LATENT_HEAT_H2O_KJ_PER_KG,
)
from ..supporting_data.infrastructure import CARBONATION_FACTORY_UNIT_PER_KG_PRODUCT_H


COMMON_DEFAULTS = MappingProxyType({
    "carbonation_factory_unit_per_kg_product_h": CARBONATION_FACTORY_UNIT_PER_KG_PRODUCT_H,
    # Preserve existing integer API values used in saved calculation hashes.
    "reactor_volume_m3": int(PICCINNO_REACTOR_VOLUME_M3),
    "solid_density_kg_per_m3": 2600,
    "water_density_kg_per_m3": 1000,
    "t0_C": 20,
    "co2_loss_fraction": .1,
    "final_product_moisture": .03,  # Applied only when drying is enabled.
    "eta_heating": .8,
    "eta_drying": .8,
    "compressor_efficiency": .7,
    "gas_efficiency": PICCINNO_GAS_EFFICIENCY,
    "gas_tank_diameter_m": PICCINNO_TANK_DIAMETER_M,
    "gas_delta_p_pa": None,
    "chamber_control_kwh_per_m3_h": .1,  # Chamber mode, per nominal volume.
    "mixing_power_number": PICCINNO_MIXING_POWER_NUMBER,
    "impeller_speed_per_s": PICCINNO_IMPELLER_SPEED_PER_S,
    "impeller_diameter_m": PICCINNO_IMPELLER_DIAMETER_M,
    "stirring_efficiency": PICCINNO_STIRRING_EFFICIENCY,
    "cp_solid_kj_per_kgK": CP_SOLID_DEFAULT_KJ_PER_KG_K,
    "cp_water_kj_per_kgK": CP_LIQUID_WATER_KJ_PER_KG_K,
    "hold_loss_kj_per_kg_h_per_deltaT100K": 22,
    "lambda_vap_kj_per_kg": int(LATENT_HEAT_H2O_KJ_PER_KG),
    "drying_delta_t_K": 80,
    "pressurization_temperature_K": 293.15,
    "reaction_phase": None,
    "reaction_heat_utilization_factor": 1,
    "reaction_heat_kj_per_mol_co2": 0,
    "reaction_heat_credit_kj": 0,
})

WET_DEFAULTS = MappingProxyType({
    "reactor_fill_fraction": .8,
    "water_recycle_ratio": .8,  # Filtrate recycle, when separation is enabled.
    "initial_cake_moisture": .12,
    "e_filtration_kwh_per_kg_dry_feed": .0055,
})

DRY_AND_SEMI_DRY_DEFAULTS = MappingProxyType({
    "dry_gas_delta_p_pa": 3000,
    "chamber_loading_kg_per_m3": 300,  # Per nominal volume, no wet fill factor.
})

DEFAULTS = MappingProxyType({
    **COMMON_DEFAULTS, **WET_DEFAULTS, **DRY_AND_SEMI_DRY_DEFAULTS,
})

AMBIENT_PRESSURE_PA = 101325
BATCH_LOADING_VOLUME_BASIS = "total_reactor"
