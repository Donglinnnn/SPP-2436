"""Editable carbonation modelling assumptions and the general UI contract.

These defaults are scenario starting points, not universal material properties or
measurements. The operating equations live in models/retained_carbonation.py.
"""
from copy import deepcopy
from dataclasses import asdict, dataclass, field, replace
from math import isfinite
from typing import Any, Dict, Optional

from ..supporting_data.carbonation_reactions import REACTION_HEAT_LIBRARY_KJ_PER_MOL_CO2
from ..supporting_data.physical_constants import CO2_MOLAR_MASS_KG_PER_MOL
from ..parameters import MASS_RATIO, json_spec, number, text_spec
from .carbonation_defaults import AMBIENT_PRESSURE_PA, BATCH_LOADING_VOLUME_BASIS, DEFAULTS


# Route presets define which unit operations are available by default. Numeric
# operating conditions such as L/S ratio, pressure, gas flow, and operation
# energy should come from the case builder or an explicit scenario.
CARBONATION_ROUTE_PRESETS: Dict[str, Dict[str, Any]] = {
    "dry_semi_dry_gas_solid": {
        "liquid_to_solid_ratio": 0.0,
        "gas_circulation": True,
        "pressurization": False,
        "mixing": False,
        "heating": False,
        "clarifier": False,
        "centrifuge": False,
        "filtration": False,
        "drying": False,
        "wastewater": False,
        "comment": "Dry or semi-dry gas-solid carbonation route.",
    },
    "wet_low_water": {
        "liquid_to_solid_ratio": 0.0,
        "gas_circulation": True,
        "pressurization": False,
        "mixing": True,
        "heating": False,
        "clarifier": False,
        "centrifuge": False,
        "filtration": False,
        "drying": False,
        "wastewater": False,
        "comment": "Low-water wet or humidified-solid carbonation route.",
    },
    "slurry_high_water": {
        "liquid_to_solid_ratio": 0.0,
        "gas_circulation": True,
        "pressurization": False,
        "mixing": True,
        "heating": False,
        "clarifier": True,
        "centrifuge": True,
        "filtration": False,
        "drying": False,
        "wastewater": True,
        "comment": "Wet slurry carbonation route.",
    },
    "pressurized_slurry": {
        "liquid_to_solid_ratio": 0.0,
        "gas_circulation": False,
        "pressurization": True,
        "mixing": True,
        "heating": False,
        "clarifier": True,
        "centrifuge": True,
        "filtration": False,
        "drying": False,
        "wastewater": True,
        "comment": "Pressurized wet slurry carbonation route.",
    },
}


@dataclass
class CarbonationMaterialSettings:
    co2_uptake_kg: float

    def __post_init__(self) -> None:
        if self.co2_uptake_kg < 0:
            raise ValueError("co2_uptake_kg must be non-negative.")


@dataclass
class CarbonationRouteSettings:
    carbonation_route: str = "lab_benchmark"

    def __post_init__(self) -> None:
        valid_routes = {"lab_benchmark", *CARBONATION_ROUTE_PRESETS.keys()}
        if self.carbonation_route not in valid_routes:
            raise ValueError(
                f"carbonation_route must be one of {sorted(valid_routes)}."
            )


@dataclass
class CarbonationProcessSettings:
    """Equation inputs after route conditions have been resolved.

    Shared coefficients use the web defaults. Required keyword-only fields are
    route-dependent values supplied by the operating-conditions adapter; they
    must not silently select a wet/dry route, moisture state or reaction time.
    Use run_calculation() for the same route resolution as the website.
    """
    # Water and CO2 balance
    liquid_to_solid_ratio: Optional[float] = field(kw_only=True)
    water_kg: Optional[float] = None
    water_recycle_ratio: float = field(kw_only=True)
    water_loss_kg: float = 0.0
    water_purge_kg: Optional[float] = None
    wastewater_out_kg: Optional[float] = None
    co2_loss_fraction: float = DEFAULTS["co2_loss_fraction"]

    # Batch scale
    reactor_volume_m3: float = DEFAULTS["reactor_volume_m3"]
    active_slurry_volume_m3: Optional[float] = None
    reactor_fill_fraction: float = DEFAULTS["reactor_fill_fraction"]
    batch_loading_kg_per_m3: Optional[float] = field(kw_only=True)
    batch_loading_volume_basis: str = BATCH_LOADING_VOLUME_BASIS
    water_density_kg_per_m3: float = DEFAULTS["water_density_kg_per_m3"]
    solid_density_kg_per_m3: float = DEFAULTS["solid_density_kg_per_m3"]
    carbonation_factory_unit_per_kg_product_h: float = DEFAULTS["carbonation_factory_unit_per_kg_product_h"]

    # Reaction and heat
    t_reaction_h: float = field(kw_only=True)
    t0_C: float = DEFAULTS["t0_C"]
    t_reaction_C: float = field(kw_only=True)
    cp_solid_kj_per_kgK: float = DEFAULTS["cp_solid_kj_per_kgK"]
    cp_water_kj_per_kgK: float = DEFAULTS["cp_water_kj_per_kgK"]
    eta_heating: float = DEFAULTS["eta_heating"]
    reaction_phase: Optional[str] = None
    reaction_heat_kj_per_mol_co2: float = DEFAULTS["reaction_heat_kj_per_mol_co2"]
    reaction_heat_utilization_factor: float = DEFAULTS["reaction_heat_utilization_factor"]
    co2_molar_mass_kg_per_mol: float = CO2_MOLAR_MASS_KG_PER_MOL
    reaction_heat_credit_kj: float = DEFAULTS["reaction_heat_credit_kj"]
    heat_loss_kj: float = 0.0
    hold_loss_kj_per_kg_h_per_deltaT100K: float = DEFAULTS["hold_loss_kj_per_kg_h_per_deltaT100K"]

    # Drying
    eta_drying: float = DEFAULTS["eta_drying"]
    evaporated_water_kg: Optional[float] = 0.0
    initial_cake_moisture: Optional[float] = field(kw_only=True)
    final_product_moisture: Optional[float] = field(kw_only=True)
    lambda_vap_kj_per_kg: float = DEFAULTS["lambda_vap_kj_per_kg"]
    drying_delta_t_K: float = DEFAULTS["drying_delta_t_K"]

    # Gas circulation
    gas_flow_rate_L_per_h: Optional[float] = None
    gas_flow_rate_m3_per_s: float = 0.0
    gas_delta_p_pa: Optional[float] = None
    gas_tank_diameter_m: float = DEFAULTS["gas_tank_diameter_m"]
    gas_slurry_density_kg_per_m3: Optional[float] = None
    gas_efficiency: float = DEFAULTS["gas_efficiency"]
    # Inactive channel. Chamber mode uses the nominal-volume duty resolved by
    # the adapter, not the low-level model's occupied-volume fallback.
    chamber_control_kwh_per_m3_h: float = 0.0

    # Pressurization
    pressurization_p1_pa: float = AMBIENT_PRESSURE_PA
    pressurization_p2_pa: float = AMBIENT_PRESSURE_PA
    pressurization_temperature_K: float = DEFAULTS["pressurization_temperature_K"]
    compressor_efficiency: float = DEFAULTS["compressor_efficiency"]

    # Mixing and stirring
    mixing_power_number: Optional[float] = DEFAULTS["mixing_power_number"]
    mixture_density_kg_per_m3: Optional[float] = None
    impeller_speed_per_s: Optional[float] = DEFAULTS["impeller_speed_per_s"]
    impeller_diameter_m: Optional[float] = DEFAULTS["impeller_diameter_m"]
    stirring_efficiency: Optional[float] = DEFAULTS["stirring_efficiency"]

    # Separation
    e_clarifier_kwh_per_kg_slurry: float = 0.0
    e_centrifuge_kwh_per_kg_slurry: float = 0.0
    e_filtration_kwh_per_kg_dry_feed: float = DEFAULTS["e_filtration_kwh_per_kg_dry_feed"]

    # Optional direct overrides
    heating_kwh_override: Optional[float] = None
    gas_circulation_kwh_override: Optional[float] = None
    # Total P3 electricity per kg dry feed, replacing both compression terms.
    pressurization_kwh_override: Optional[float] = None
    mixing_kwh_override: Optional[float] = None
    clarifier_kwh_override: Optional[float] = None
    centrifuge_kwh_override: Optional[float] = None
    filtration_kwh_override: Optional[float] = None
    drying_kwh_override: Optional[float] = None

    include: Dict[str, bool] = field(default_factory=dict)
    include_was_provided: bool = False

    def __post_init__(self) -> None:
        if (type(self.t_reaction_h) not in (int, float)
                or not isfinite(self.t_reaction_h) or self.t_reaction_h <= 0):
            raise ValueError("t_reaction_h must be a supplied finite number greater than zero.")
        if (type(self.carbonation_factory_unit_per_kg_product_h) not in (int, float)
                or not isfinite(self.carbonation_factory_unit_per_kg_product_h)
                or self.carbonation_factory_unit_per_kg_product_h < 0):
            raise ValueError("carbonation_factory_unit_per_kg_product_h must be finite and non-negative.")
        non_negative_values = {
            "liquid_to_solid_ratio": self.liquid_to_solid_ratio,
            "water_kg": self.water_kg,
            "water_loss_kg": self.water_loss_kg,
            "water_purge_kg": self.water_purge_kg,
            "wastewater_out_kg": self.wastewater_out_kg,
            "reactor_volume_m3": self.reactor_volume_m3,
            "active_slurry_volume_m3": self.active_slurry_volume_m3,
            "batch_loading_kg_per_m3": self.batch_loading_kg_per_m3,
            "carbonation_factory_unit_per_kg_product_h": self.carbonation_factory_unit_per_kg_product_h,
            "t_reaction_h": self.t_reaction_h,
            "evaporated_water_kg": self.evaporated_water_kg,
            "drying_delta_t_K": self.drying_delta_t_K,
            "gas_flow_rate_L_per_h": self.gas_flow_rate_L_per_h,
            "gas_flow_rate_m3_per_s": self.gas_flow_rate_m3_per_s,
            "gas_delta_p_pa": self.gas_delta_p_pa,
            "gas_tank_diameter_m": self.gas_tank_diameter_m,
            "gas_slurry_density_kg_per_m3": self.gas_slurry_density_kg_per_m3,
            "chamber_control_kwh_per_m3_h": self.chamber_control_kwh_per_m3_h,
            "pressurization_p1_pa": self.pressurization_p1_pa,
            "pressurization_p2_pa": self.pressurization_p2_pa,
            "pressurization_temperature_K": self.pressurization_temperature_K,
            "mixing_power_number": self.mixing_power_number,
            "mixture_density_kg_per_m3": self.mixture_density_kg_per_m3,
            "impeller_speed_per_s": self.impeller_speed_per_s,
            "impeller_diameter_m": self.impeller_diameter_m,
            "reaction_heat_kj_per_mol_co2": self.reaction_heat_kj_per_mol_co2,
            "reaction_heat_credit_kj": self.reaction_heat_credit_kj,
            "co2_molar_mass_kg_per_mol": self.co2_molar_mass_kg_per_mol,
            "e_clarifier_kwh_per_kg_slurry": self.e_clarifier_kwh_per_kg_slurry,
            "e_centrifuge_kwh_per_kg_slurry": self.e_centrifuge_kwh_per_kg_slurry,
            "e_filtration_kwh_per_kg_dry_feed": self.e_filtration_kwh_per_kg_dry_feed,
            "heating_kwh_override": self.heating_kwh_override,
            "gas_circulation_kwh_override": self.gas_circulation_kwh_override,
            "pressurization_kwh_override": self.pressurization_kwh_override,
            "mixing_kwh_override": self.mixing_kwh_override,
            "clarifier_kwh_override": self.clarifier_kwh_override,
            "centrifuge_kwh_override": self.centrifuge_kwh_override,
            "filtration_kwh_override": self.filtration_kwh_override,
            "drying_kwh_override": self.drying_kwh_override,
        }
        for label, value in non_negative_values.items():
            if value is not None and value < 0:
                raise ValueError(f"{label} must be non-negative.")
        if not 0 <= self.reaction_heat_utilization_factor <= 1:
            raise ValueError("reaction_heat_utilization_factor must be between 0 and 1.")
        if not 0 <= self.water_recycle_ratio <= 1:
            raise ValueError("water_recycle_ratio must be between 0 and 1.")
        if not 0 <= self.co2_loss_fraction < 1:
            raise ValueError("co2_loss_fraction must be >= 0 and < 1.")
        if self.reactor_fill_fraction <= 0 or self.reactor_fill_fraction > 1:
            raise ValueError("reactor_fill_fraction must be > 0 and <= 1.")
        if self.batch_loading_volume_basis != "total_reactor":
            raise ValueError("batch_loading_volume_basis must be total_reactor.")
        if self.water_density_kg_per_m3 <= 0 or self.solid_density_kg_per_m3 <= 0:
            raise ValueError("water and solid densities must be positive.")
        if self.co2_molar_mass_kg_per_mol <= 0:
            raise ValueError("co2_molar_mass_kg_per_mol must be positive.")
        if (
            self.reaction_phase is not None
            and self.reaction_phase not in REACTION_HEAT_LIBRARY_KJ_PER_MOL_CO2
        ):
            valid = ", ".join(sorted(REACTION_HEAT_LIBRARY_KJ_PER_MOL_CO2))
            raise ValueError(f"reaction_phase must be one of: {valid}.")
        if self.gas_tank_diameter_m <= 0:
            raise ValueError("gas_tank_diameter_m must be positive.")
        if (
            self.gas_slurry_density_kg_per_m3 is not None
            and self.gas_slurry_density_kg_per_m3 <= 0
        ):
            raise ValueError("gas_slurry_density_kg_per_m3 must be positive.")
        if (
            self.eta_heating <= 0
            or self.eta_drying <= 0
            or self.gas_efficiency <= 0
            or self.compressor_efficiency <= 0
        ):
            raise ValueError("Energy conversion efficiencies must be positive.")
        if self.stirring_efficiency is not None and self.stirring_efficiency <= 0:
            raise ValueError("stirring_efficiency must be positive.")
        for label, value in {
            "initial_cake_moisture": self.initial_cake_moisture,
            "final_product_moisture": self.final_product_moisture,
        }.items():
            if value is not None and not 0 <= value < 1:
                raise ValueError(f"{label} must be >= 0 and < 1.")
        if (
            self.initial_cake_moisture is not None
            and self.final_product_moisture is not None
            and self.final_product_moisture > self.initial_cake_moisture
        ):
            raise ValueError("final_product_moisture cannot exceed initial_cake_moisture.")


GENERAL_VARIANT = "general_operating_v2"
INPUT_DEFAULTS_VERSION = "carbonation-route-specific-fill-2026-10-v5"
GENERAL_CONDITION_SPECS = {
    "carbonation_model": text_spec(required=True, choices=(GENERAL_VARIANT,)),
    "co2_uptake_kg": number("kg/kg solid", required=True, conversions=MASS_RATIO),
    "t_reaction_h": number("h", required=True, exclusive_minimum=True, conversions={"min": 1 / 60}),
    "condition_inputs": json_spec(required=True, description="Water, heat, pressure and gas operating conditions; optional background_overrides. Wet fill fraction and dry solids loading are route-specific."),
}

# These are editable modelling defaults, not measured properties. Several
# originated in earlier case assumptions; review them for each new system.
# Values come exclusively from carbonation_defaults.py; keep field contracts here.
BACKGROUND = {
    "carbonation_factory_unit_per_kg_product_h": number("unit/(kg dry product h)",
        description="Carbonation factory use per kg dry product and reaction hour."),
    "reactor_volume_m3": number("m3", exclusive_minimum=True),
    "reactor_fill_fraction": number("fraction", exclusive_minimum=True, maximum=1,
                                    description="Wet-slurry reactor fill fraction; not used by dry or semi-dry routes."),
    "solid_density_kg_per_m3": number("kg/m3", exclusive_minimum=True),
    "water_density_kg_per_m3": number("kg/m3", exclusive_minimum=True),
    "t0_C": number("deg C", minimum=-273.15, exclusive_minimum=True),
    "water_recycle_ratio": number("fraction", maximum=1),
    "co2_loss_fraction": number("fraction", maximum=1),
    "initial_cake_moisture": number("wet mass fraction", maximum=1),
    "final_product_moisture": number("wet mass fraction", maximum=1),
    "e_filtration_kwh_per_kg_dry_feed": number("kWh/kg dry feed"),
    "eta_heating": number("fraction", exclusive_minimum=True, maximum=1),
    "eta_drying": number("fraction", exclusive_minimum=True, maximum=1),
    "compressor_efficiency": number("fraction", exclusive_minimum=True, maximum=1),
    "gas_efficiency": number("fraction", exclusive_minimum=True, maximum=1),
    "gas_tank_diameter_m": number("m", exclusive_minimum=True),
    "gas_delta_p_pa": number("Pa", description="Optional override; wet flow otherwise uses slurry head."),
    "dry_gas_delta_p_pa": number("Pa"),
    "chamber_control_kwh_per_m3_h": number("kWh/(m3 h)"),
    "chamber_loading_kg_per_m3": number("kg dry feed/m3", exclusive_minimum=True,
                                        description="Dry and semi-dry batch loading per nominal reactor volume; not used by wet slurry routes."),
    "mixing_power_number": number(),
    "impeller_speed_per_s": number("1/s"),
    "impeller_diameter_m": number("m", exclusive_minimum=True),
    "stirring_efficiency": number("fraction", exclusive_minimum=True, maximum=1),
    "cp_solid_kj_per_kgK": number("kJ/(kg K)", exclusive_minimum=True),
    "cp_water_kj_per_kgK": number("kJ/(kg K)", exclusive_minimum=True),
    "hold_loss_kj_per_kg_h_per_deltaT100K": number("kJ/(kg h 100K)"),
    "lambda_vap_kj_per_kg": number("kJ/kg water", exclusive_minimum=True),
    "drying_delta_t_K": number("K"),
    "pressurization_temperature_K": number("K", exclusive_minimum=True),
    "reaction_phase": text_spec(choices=tuple(REACTION_HEAT_LIBRARY_KJ_PER_MOL_CO2)),
    # Credit is active by default only when a reaction phase or heat value is supplied.
    "reaction_heat_utilization_factor": number("fraction", maximum=1),
    "reaction_heat_kj_per_mol_co2": number("kJ/mol CO2"),
    "reaction_heat_credit_kj": number("kJ/kg dry feed"),
}
BACKGROUND = {key: replace(spec, default=DEFAULTS[key]) for key, spec in BACKGROUND.items()}


def carbonation_defaults_library(model_variant=GENERAL_VARIANT):
    if model_variant != GENERAL_VARIANT:
        raise ValueError("Unsupported carbonation model variant")
    return {
        "description": "Editable engineering scenario defaults; not universal or measured material properties.",
        "parameters": {key: asdict(spec) for key, spec in BACKGROUND.items()},
        "reaction_heat_library": deepcopy(REACTION_HEAT_LIBRARY_KJ_PER_MOL_CO2),
        "energy_supply": "Equipment electricity and process heat are separate foreground exchanges; background LCIA is resolved by the selected energy markets.",
        "sources": [
            "SPPFramework_1608/source_snapshot/Carbonation.py: retained operating equations.",
            "Author's SI S1.3 and case assumptions supplied initial engineering defaults; review or override for a new system.",
        ],
    }
