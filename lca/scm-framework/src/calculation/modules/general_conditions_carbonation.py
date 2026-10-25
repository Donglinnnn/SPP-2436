"""General operating-conditions adapter for carbonation.

The retained pure model owns the equations. This adapter resolves editable
scenario assumptions, scales gas flow, and normalizes the foreground inventory.
Wet fill fraction and dry solids loading are separate route-specific inputs.
"""
from dataclasses import asdict, replace
from math import isfinite

from ..process_settings.carbonation import (BACKGROUND, GENERAL_CONDITION_SPECS,
    GENERAL_VARIANT, carbonation_defaults_library,
    CarbonationMaterialSettings, CarbonationProcessSettings)
from ..process_settings.carbonation_defaults import AMBIENT_PRESSURE_PA, BATCH_LOADING_VOLUME_BASIS
from ..models.retained_carbonation import GeneralCarbonationProcess
from ..supporting_data.infrastructure import CARBONATION_FACTORY_SOURCE
from ..parameters import Parameters
from .common import calculated_result
from .operating_inputs import numeric, switch


def resolve_inputs(params):
    supplied = params.values["condition_inputs"]
    allowed = {"water_mode", "water_powder_ratio", "heat_up", "target_temperature_C",
               "pressurize", "target_pressure_bar", "gas_mode", "gas_flow_basis", "gas_flow_L_h",
               "gas_flow_L_h_per_kg_feed", "gas_lab_feed_kg", "chamber_volume_m3",
               "chamber_co2_concentration_vol_pct", "separation",
               "drying", "mixing", "background_overrides", "batch_loading_volume_basis"}
    if not isinstance(supplied, dict) or set(supplied) - allowed:
        raise ValueError("condition_inputs must contain supported operating-condition fields")
    c = supplied
    overrides = c.get("background_overrides", {})
    if not isinstance(overrides, dict) or set(overrides) - set(BACKGROUND):
        raise ValueError("background_overrides contains unsupported parameters")
    b = {key: spec.default for key, spec in BACKGROUND.items()}
    origins = {key: "editable_scenario_default" for key in b}
    for key, value in overrides.items():
        spec = BACKGROUND[key]
        if value is None and spec.default is None:
            b[key] = None
        elif spec.kind == "string":
            if not isinstance(value, str) or value not in spec.choices:
                raise ValueError(f"{key}: choose a supported reaction phase")
            b[key] = value
        else:
            b[key] = numeric(overrides, key, minimum=spec.minimum, positive=spec.exclusive_minimum)
            if spec.maximum is not None and b[key] > spec.maximum:
                raise ValueError(f"{key}: exceeds {spec.maximum}")
        origins[key] = "provided_override"
    for key in ("co2_loss_fraction", "initial_cake_moisture", "final_product_moisture"):
        if b[key] >= 1:
            raise ValueError(f"{key}: must be less than 1")
    if ("reaction_heat_utilization_factor" in overrides and b["reaction_heat_utilization_factor"] > 0
            and b["reaction_phase"] is None and b["reaction_heat_kj_per_mol_co2"] <= 0):
        raise ValueError("Reaction heat utilization requires a reaction phase or explicit heat value")
    return c, b, origins


def calculate_general_conditions(process_input):
    params = Parameters(process_input, GENERAL_CONDITION_SPECS)
    c, b, origins = resolve_inputs(params)
    variant = params.values["carbonation_model"]
    library = carbonation_defaults_library(variant)
    mode, gas = c.get("water_mode", "dry"), c.get("gas_mode", "none")
    if mode not in ("dry", "semi_dry", "wet") or gas not in ("none", "flow", "chamber"):
        raise ValueError("Choose a supported water and gas mode")
    # Dry and semi-dry routes use nominal reactor volume; wet routes derive
    # batch mass from their slurry fill fraction.
    loading_basis = c.get("batch_loading_volume_basis", BATCH_LOADING_VOLUME_BASIS)
    if loading_basis != BATCH_LOADING_VOLUME_BASIS:
        raise ValueError("Dry and semi-dry loading requires nominal reactor volume")
    if mode != "wet" and "reactor_fill_fraction" in c.get("background_overrides", {}):
        raise ValueError("reactor_fill_fraction is a wet-route input")
    water = 0 if mode == "dry" else numeric(c, "water_powder_ratio", positive=True)
    heat, press = switch(c, "heat_up"), switch(c, "pressurize")
    separation = switch(c, "separation", mode == "wet") and mode == "wet"
    drying = switch(c, "drying", mode == "wet") and mode != "dry"
    # Slurry stirring is part of the wet route, not a separate user choice.
    mixing = mode == "wet"
    temperature = numeric(c, "target_temperature_C", minimum=b["t0_C"], positive=True) if heat else b["t0_C"]
    pressure = numeric(c, "target_pressure_bar", minimum=AMBIENT_PRESSURE_PA / 100000, positive=True) * 100000 if press else AMBIENT_PRESSURE_PA
    if press and mode == "wet" and b["reactor_fill_fraction"] >= 1:
        raise ValueError("Pressurization requires a reactor fill fraction below 1")
    product = 1 + params.values["co2_uptake_kg"]
    initial = b["initial_cake_moisture"] if separation else water / (product + water)
    if separation and drying and b["final_product_moisture"] > initial:
        raise ValueError("Drying target moisture exceeds wet-cake moisture")
    final = min(initial, b["final_product_moisture"]) if drying else initial
    settings = {key: value for key, value in b.items() if key not in {
        "dry_gas_delta_p_pa", "chamber_control_kwh_per_m3_h", "chamber_loading_kg_per_m3"}}
    settings.update(liquid_to_solid_ratio=water, initial_cake_moisture=initial, final_product_moisture=final,
        water_recycle_ratio=b["water_recycle_ratio"] if separation else 0,
        t_reaction_h=params.values["t_reaction_h"], t_reaction_C=temperature,
        pressurization_p1_pa=AMBIENT_PRESSURE_PA, pressurization_p2_pa=pressure,
        gas_delta_p_pa=b["gas_delta_p_pa"] if b["gas_delta_p_pa"] is not None else (None if mode == "wet" else b["dry_gas_delta_p_pa"]),
        batch_loading_kg_per_m3=None if mode == "wet" else b["chamber_loading_kg_per_m3"],
        batch_loading_volume_basis=loading_basis,
        include={"gas_circulation": gas != "none", "pressurization": press, "mixing": mixing, "heating": heat,
                 "filtration": separation, "clarifier": False, "centrifuge": False, "drying": drying},
        include_was_provided=True)
    model = GeneralCarbonationProcess(CarbonationMaterialSettings(params.values["co2_uptake_kg"]), CarbonationProcessSettings(**settings))
    flow, specific_flow, chamber_batch, chamber_volume = 0, None, None, None
    chamber_co2_concentration = None
    flow_basis = c.get("gas_flow_basis", "per_reactor")
    if flow_basis not in ("per_reactor", "per_kg_feed", "lab_batch"):
        raise ValueError("gas_flow_basis must be per_reactor, per_kg_feed or lab_batch")
    if gas == "flow":
        if flow_basis == "per_reactor":
            flow = numeric(c, "gas_flow_L_h", positive=True)
            specific_flow = flow / model.feed_batch_kg()
        elif flow_basis == "per_kg_feed":
            specific_flow = numeric(c, "gas_flow_L_h_per_kg_feed", positive=True)
            flow = specific_flow * model.feed_batch_kg()
        else:
            specific_flow = numeric(c, "gas_flow_L_h", positive=True) / numeric(c, "gas_lab_feed_kg", positive=True)
            flow = specific_flow * model.feed_batch_kg()
        if not isfinite(flow):
            raise ValueError("Gas-flow scaling overflow; check flow and dry batch mass")
        model.process = replace(model.process, gas_flow_rate_L_per_h=flow)
    elif gas == "chamber":
        chamber_volume = numeric(c, "chamber_volume_m3", default=b["reactor_volume_m3"], positive=True)
        # Use one stated chamber volume for the batch and chamber-control demand.
        model.process = replace(model.process, reactor_volume_m3=chamber_volume)
        if c.get("chamber_co2_concentration_vol_pct") not in (None, ""):
            chamber_co2_concentration = numeric(c, "chamber_co2_concentration_vol_pct", positive=True)
            if chamber_co2_concentration > 100:
                raise ValueError("chamber_co2_concentration_vol_pct must not exceed 100")
        chamber_batch = model.feed_batch_kg()
        duty = b["chamber_control_kwh_per_m3_h"] * chamber_volume * params.values["t_reaction_h"] / chamber_batch
        model.process = replace(model.process, gas_circulation_kwh_override=duty)
    if mode != "wet":
        occupied = model.active_slurry_volume_m3()
        reactor = model.process.reactor_volume_m3
        if occupied > reactor:
            raise ValueError("Dry solid and water volumes exceed the reactor volume")
        if press and occupied >= reactor:
            raise ValueError("Pressurization requires free gas volume in the dry reactor")
    raw = model.inventory_per_kg_dry_input()
    thermal = {"heating": raw["heating_kwh"], "drying": raw["drying_kwh"]}
    electricity = {"gas_handling": raw["gas_circulation_kwh"], "headspace_pressurization": raw["headspace_pressurization_kwh"],
                   "co2_makeup_compression": raw["co2_makeup_compression_kwh"],
                   "mixing": raw["mixing_kwh"], "separation": raw["filtration_kwh"]}
    if model.process.pressurization_kwh_override is not None:
        electricity["pressurization_override"] = raw["pressurization_override_kwh"]
    # Equipment electricity excludes both thermal duties.
    params.warnings.extend([
        "Heating and drying are process heat; gas handling, pressurization, mixing and separation are equipment electricity.",
        "CO2 uptake is supplied, not predicted. Heat utilization and moisture defaults are editable modelling assumptions, not universal measurements.",
        "Foreground inventory only; upstream CO2 supply and background LCIA are not calculated. CO2 loss and storage are physical masses, not a net climate benefit.",
    ])
    if not separation and drying:
        params.warnings.append("No separation: drying removes water from the whole wet feed, not a fictitious separated cake.")
    if mode != "dry":
        params.warnings.append("Dry-product basis; product water is separate. Recycle assumes steady-state reuse.")
    detail = {
        "effective_conditions": {"water_mode": mode, "water_powder_ratio": water, "heat_up": heat,
            "target_temperature_C": temperature, "pressurize": press, "target_pressure_bar": pressure / 100000,
            "gas_mode": gas, "gas_flow_basis": flow_basis, "gas_flow_L_h": flow,
            "gas_flow_L_h_per_kg_feed": specific_flow, "chamber_volume_m3": chamber_volume,
            "separation": separation, "drying": drying, "mixing": mixing},
        "product_mass_kg_per_kg_dry_input": product,
        "gas_handling_batch_kg": chamber_batch if gas == "chamber" else raw["feed_batch_kg"],
        "electricity_components_kwh_per_kg_dry_input": electricity,
        "heat_components_kwh_per_kg_dry_input": thermal,
        "thermal_demand_components_kwh_per_kg_dry_input": thermal,
        "pressurization_accounting": {
            "scope": "Reactor headspace charging plus external makeup CO2 compression.",
            "basis": "kWh per kg dry feed",
            "source_reference": "SI1-3_ParameterAndInventories.xlsx, S1.3 Carbonation, F86-F88",
            "override_scope": "A supplied pressurization_kwh_override replaces total P3.",
        },
        "factory_use": {
            "coefficient_unit_per_kg_dry_product_h": b["carbonation_factory_unit_per_kg_product_h"],
            "reaction_time_h": params.values["t_reaction_h"],
            "unit_per_kg_dry_product": raw["carbonation_factory_unit"] / product,
            "origin": origins["carbonation_factory_unit_per_kg_product_h"],
            "default_source_reference": CARBONATION_FACTORY_SOURCE,
        },
        "reaction_heat_credit_kj_per_kg_dry_input": raw["reaction_heat_credit_kj"],
        "background_parameters": {
            key: {"value": value, "unit": BACKGROUND[key].unit, "origin": origins[key]}
            for key, value in b.items()
            if (mode == "wet" and key != "chamber_loading_kg_per_m3")
            or (mode != "wet" and key != "reactor_fill_fraction")},
        "effective_model_settings": asdict(model.process),
        "mass_balance_per_kg_dry_input": {key: value for key, value in raw.items() if key.endswith("_kg")},
        "energy_supply": library["energy_supply"], "sources": library["sources"],
        "inventory_aliases": {"co2_emitted_kg": "Same physical flow as co2_makeup_loss_kg; do not add the two."},
    }
    if mode == "wet":
        detail["effective_model_settings"].pop("batch_loading_kg_per_m3")
        detail["effective_model_settings"].pop("batch_loading_volume_basis")
        detail["batch_loading"] = {
            "route": mode,
            "volume_basis": "wet_slurry_fill",
            "reactor_volume_m3": model.process.reactor_volume_m3,
            "wet_reactor_fill_fraction": model.process.reactor_fill_fraction,
            "active_slurry_volume_m3": raw["active_slurry_volume_m3"],
            "free_gas_volume_m3": raw["headspace_volume_m3"],
            "dry_feed_batch_kg": raw["feed_batch_kg"],
        }
    else:
        detail["effective_model_settings"].pop("reactor_fill_fraction")
        detail["batch_loading"] = {
            "route": mode,
            "volume_basis": "total_reactor",
            "loading_volume_m3": model.process.reactor_volume_m3,
            "loading_kg_dry_feed_per_m3": model.process.batch_loading_kg_per_m3,
            "dry_feed_batch_kg": raw["feed_batch_kg"],
            "occupied_solid_water_volume_m3": raw["active_slurry_volume_m3"],
            "free_gas_volume_m3": raw["headspace_volume_m3"],
        }
    if gas == "chamber":
        detail["reported_chamber_conditions"] = {
            "co2_concentration_vol_pct": chamber_co2_concentration,
            "concentration_role": "record_only_not_used_in_calculation",
        }
    inventory = {"upstream_input_kg": 1, "electricity_kwh": sum(electricity.values()),
        "heat_kwh": sum(thermal.values()),
        "carbonation_factory_unit": raw["carbonation_factory_unit"],
        "water_input_kg": raw["freshwater_makeup_kg"], "wastewater_treatment_kg": raw["wastewater_kg"],
        "co2_stored_kg": params.values["co2_uptake_kg"], "co2_makeup_kg": raw["co2_makeup_kg"],
        "co2_makeup_loss_kg": raw["co2_lost_kg"], "co2_emitted_kg": raw["co2_lost_kg"],
        "water_evaporated_kg": raw["evaporated_water_kg"], "water_in_product_kg": raw["final_product_water_kg"]}
    result = calculated_result(process_input, params, {key: value / product for key, value in inventory.items()}, detail,
                               source_file="src/calculation/models/retained_carbonation.py")
    result.metadata["model_variant"] = GENERAL_VARIANT
    result.metadata["recording"] = {
        "native_basis": "per kg dry processed input", "native_inventory": dict(inventory),
        "normalization_factor_to_process_product": 1.0 / product,
        "normalization_note": "Dry product mass equals dry input plus supplied CO2 uptake. Effective operating conditions and engineering assumptions are in details.",
        "exchange_metadata": {
            key: {
                "generation_layer": "L1", "source_reference": "src/calculation/models/retained_carbonation.py:GeneralCarbonationProcess",
                "parameter_codes": ["co2_uptake_kg", "t_reaction_h", "condition_inputs"],
                "role": role, "exchange_type": exchange_type, "unit": unit,
            } for key, role, exchange_type, unit in (
                ("upstream_input_kg", "exchange", "technosphere", "kg"),
                ("electricity_kwh", "exchange", "technosphere", "kWh"),
                ("heat_kwh", "exchange", "technosphere", "kWh"),
                ("water_input_kg", "exchange", "technosphere", "kg"),
                ("wastewater_treatment_kg", "exchange", "technosphere", "kg"),
                ("co2_stored_kg", "diagnostic", "unclassified", "kg"),
                ("co2_makeup_kg", "exchange", "technosphere", "kg"),
                ("co2_makeup_loss_kg", "exchange", "elementary", "kg"),
                ("co2_emitted_kg", "alias", "elementary", "kg"),
                ("water_evaporated_kg", "exchange", "elementary", "kg"),
                ("water_in_product_kg", "diagnostic", "unclassified", "kg"),
            )
        },
    }
    exchange_metadata = result.metadata["recording"]["exchange_metadata"]
    exchange_metadata["carbonation_factory_unit"] = {
        "generation_layer": None,
        "source_reference": (CARBONATION_FACTORY_SOURCE
            if origins["carbonation_factory_unit_per_kg_product_h"] == "editable_scenario_default"
            else "Provided carbonation factory-use coefficient override"),
        "parameter_codes": ["t_reaction_h", "condition_inputs"],
        "role": "exchange", "exchange_type": "technosphere", "unit": "unit",
        "note": "Factory coefficient × dry product mass × reaction time on the native feed basis; divide by dry product mass once for reporting.",
    }
    for key in ("co2_emitted_kg", "co2_stored_kg"):
        # Aliases and recorded uptake have no separate formula-generated exchange.
        exchange_metadata[key]["generation_layer"] = None
    exchange_metadata["co2_emitted_kg"].update(
        alias_of="co2_makeup_loss_kg", note="Alias for the same physical CO2 loss; include this flow only once.")
    exchange_metadata["co2_stored_kg"]["note"] = (
        "CO2 retained in dry product is a mass-balance record, not an automatically assigned elementary removal or climate credit.")
    exchange_metadata["water_in_product_kg"]["note"] = "Moisture accompanying the dry product; not a separate elementary flow."
    exchange_metadata["heat_kwh"]["note"] = "Process heat from heating and drying; not included in equipment electricity_kwh."
    return result
