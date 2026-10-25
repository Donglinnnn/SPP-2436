"""Thermal-activation input contract and editable heat-model assumptions."""

from dataclasses import KW_ONLY, dataclass
from math import isfinite
from typing import Optional

from ..parameters import json_spec, number, text_spec
from .thermal_activation_defaults import (
    FREE_WATER_EVAPORATION_CUTOFF_C,
    SCENARIO_DEFAULTS,
    SETTINGS_DEFAULTS,
)


@dataclass
class StandardizedScenario:
    """Editable practical heat-up and holding-loss assumptions."""

    name: str = SCENARIO_DEFAULTS["name"]
    lambda_heatup: float = SCENARIO_DEFAULTS["lambda_heatup"]
    hold_loss_kj_per_kg_h_per_deltaT100K: float = SCENARIO_DEFAULTS["hold_loss_kj_per_kg_h_per_deltaT100K"]
    gas_exit_temperature_C: Optional[float] = SCENARIO_DEFAULTS["gas_exit_temperature_C"]


@dataclass
class ThermalActivationSettings:
    """Equation inputs with explicit route temperature and holding time.

    Holding time and subsequent overrides use keywords so positional callers cannot
    silently bind a former holding-time argument to a heat-capacity parameter.
    """
    activation_temperature_C: float
    ambient_temperature_C: float = SETTINGS_DEFAULTS["ambient_temperature_C"]
    _: KW_ONLY
    holding_time_h: float

    cp_feed_kj_per_kg_k: float = SETTINGS_DEFAULTS["cp_feed_kj_per_kg_k"]
    cp_h2o_steam_kj_per_kg_k: float = SETTINGS_DEFAULTS["cp_h2o_steam_kj_per_kg_k"]
    cp_co2_kj_per_kg_k: float = SETTINGS_DEFAULTS["cp_co2_kj_per_kg_k"]
    cp_liquid_water_kj_per_kg_k: float = SETTINGS_DEFAULTS["cp_liquid_water_kj_per_kg_k"]
    latent_heat_h2o_kj_per_kg: float = SETTINGS_DEFAULTS["latent_heat_h2o_kj_per_kg"]
    free_water_evaporation_cutoff_C: float = SETTINGS_DEFAULTS["free_water_evaporation_cutoff_C"]
    thermal_factory_unit_per_kg_product_h: float = SETTINGS_DEFAULTS["thermal_factory_unit_per_kg_product_h"]

    def __post_init__(self) -> None:
        if (isinstance(self.holding_time_h, bool)
                or not isinstance(self.holding_time_h, (int, float))
                or not isfinite(self.holding_time_h)
                or self.holding_time_h < 0):
            raise ValueError("holding_time_h must be a finite non-negative number.")


THERMAL_SPECS = {
    "tga_basis": text_spec(default="total_intervals", choices=("total_intervals",),
        description="Nonoverlapping total-loss intervals. Every loss fraction uses the same initial dry sample basis."),
    "activation_temperature_C": number("deg C", required=True),
    "holding_time_h": number("h", required=True, conversions={"min": 1 / 60}),
    "feed_composition_table": json_spec(description="Optional legacy recipe mapping component names to dry masses in kg. When omitted or blank, use one normalized kg of the single upstream material; actual feed demand is calculated from TGA yield."),
    "tga_intervals_table": json_spec(required=True, description="Nonoverlapping total-loss intervals on the initial dry sample basis: name, start_C, end_C, loss_fraction (fraction, not percent). reaction_key resolves gas shares and automatically includes reference enthalpy for a listed pure reaction."),
    "reaction_terms": json_spec(default=[], description="Optional explicit reaction heat terms. When supplied they take precedence over TGA-derived reference enthalpies."),
    "settings": json_spec(default={}, description="Optional ThermalActivationSettings overrides; temperatures are deg C, heat capacities kJ/(kg K)."),
    "scenario": json_spec(default={}, description="Optional StandardizedScenario overrides; effective values are reported in the result."),
}
