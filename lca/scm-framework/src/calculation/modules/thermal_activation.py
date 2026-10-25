from copy import deepcopy
from dataclasses import asdict, fields
from math import isfinite

from ..models.thermal_activation import (
    FeedComposition, GeneralThermalActivationProcess, ReactionTerm, TGAIntervalLoss,
)
from ..parameters import Parameters
from ..process_settings.thermal_activation import StandardizedScenario, THERMAL_SPECS, ThermalActivationSettings
from ..supporting_data.thermal_reactions import THERMAL_REACTIONS
from ..supporting_data.infrastructure import THERMAL_FACTORY_SOURCE
from .common import calculated_result


def resolve_tga_reaction(row):
    """Resolve a TGA interval and optional reference-reaction metadata."""
    if not isinstance(row, dict):
        raise ValueError("TGA interval must be an object")
    if "include_reaction_heat" in row:
        raise ValueError(
            "include_reaction_heat is not a supported input; select a reaction_key "
            "or supply explicit reaction_terms"
        )
    values = dict(row)
    key = values.pop("reaction_key", None)
    if key is None or key == "":
        return values, None
    if not isinstance(key, str) or key not in THERMAL_REACTIONS:
        raise ValueError(f"Unknown TGA reaction_key: {key!r}")
    record = deepcopy(THERMAL_REACTIONS[key])
    reference_heat_included = (record.get("kind") == "chemical_reaction"
                               and record.get("reference_enthalpy_kj_per_kg_reactant") is not None)
    for bound in ("start_C", "end_C"):
        if values.get(bound) in (None, ""):
            if record[bound] is None:
                raise ValueError(f"{key}: enter a measured {bound} for this reaction")
            values[bound] = record[bound]
    for gas in ("h2o_share", "co2_share"):
        if gas in values and (type(values[gas]) not in (int, float) or values[gas] != record[gas]):
            raise ValueError(f"{key}: {gas} conflicts with the selected reaction")
        values[gas] = record[gas]
    return values, {
        **record, "reaction_key": key, "interval_name": values.get("name"),
        "include_reaction_heat": reference_heat_included,  # Derived result key retained for existing consumers.
        "preset_start_C": record["start_C"], "preset_end_C": record["end_C"],
        "start_C": values.get("start_C"), "end_C": values.get("end_C"),
    }


def _number(value, name, minimum=0.0):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) or value < minimum:
        raise ValueError(f"{name}: expected a finite number >= {minimum}")


def _object(value, cls, label):
    if not isinstance(value, dict):
        raise ValueError(f"{label}: expected a JSON object")
    unknown = set(value) - {f.name for f in fields(cls)}
    if unknown:
        raise ValueError(f"{label}: unsupported fields: {sorted(unknown)}")
    return dict(value)


def calculate_thermal_activation(process_input):
    for record in process_input.parameters:
        if record.parameter_code.strip() == "tga_basis" and record.value.strip() == "gas_channels":
            raise ValueError(
                "tga_basis='gas_channels' is no longer supported; "
                "provide nonoverlapping total-loss intervals on the initial dry sample basis"
            )
    params = Parameters(process_input, THERMAL_SPECS)
    p = params.values
    feed = p["feed_composition_table"]
    automatic_feed = params.provenance["feed_composition_table"]["origin"] == "not_supplied"
    if automatic_feed:
        # One kg is a recipe-normalization basis, not the process throughput.
        # The existing serial chain scales the single upstream stream by TGA yield.
        feed = {"upstream_material": 1.0}
        p["feed_composition_table"] = feed
        params.provenance["feed_composition_table"].update(
            value=feed, origin="upstream_single_material_default",
            default_basis="100% single upstream material; normalized 1 kg recipe",
        )
    if not isinstance(feed, dict) or not feed:
        raise ValueError("feed_composition_table must map component names to dry recipe masses in kg")
    for name, value in feed.items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Feed component names must be nonempty strings")
        _number(value, f"feed.{name}")
    intervals = p["tga_intervals_table"]
    if not isinstance(intervals, list) or not intervals:
        raise ValueError("tga_intervals_table must be a nonempty list of mixture-level intervals")
    tga = []
    selected_reactions = []
    reference_reactions = []
    for row in intervals:
        values, reaction = resolve_tga_reaction(row)
        values = _object(values, TGAIntervalLoss, "TGA interval")
        for key, value in values.items():
            if key != "name":
                _number(value, f"TGA.{key}")
        interval = TGAIntervalLoss(**values)
        if not isinstance(interval.name, str) or not interval.name.strip():
            raise ValueError("TGA interval name must be a nonempty string")
        if interval.loss_fraction >= 1:
            raise ValueError("TGA loss_fraction must be a fraction < 1, not a percentage")
        tga.append(interval)
        if reaction:
            if reaction["include_reaction_heat"]:
                # loss_fraction is the full-interval gas mass per kg original dry
                # feed. ReactionTerm applies the temperature completion once.
                reactant_fraction = (interval.loss_fraction
                    * reaction["reactant_molar_mass_g_per_mol"]
                    / reaction["gas_molar_mass_g_per_mol"])
                if reactant_fraction > 1:
                    raise ValueError(f"{interval.name}: inferred reactant exceeds the initial dry feed; check the isolated gas loss")
                reference_reactions.append(ReactionTerm(
                    name=f"reference_{interval.name}",
                    mass_fraction_in_feed=reactant_fraction,
                    enthalpy_kJ_per_kg_reactant=reaction["reference_enthalpy_kj_per_kg_reactant"],
                    start_C=interval.start_C, end_C=interval.end_C,
                ))
                reaction["inferred_reactant_fraction_in_feed"] = reactant_fraction
            selected_reactions.append(reaction)
    ordered = sorted(tga, key=lambda interval: interval.start_C)
    if any(a.end_C > b.start_C for a, b in zip(ordered, ordered[1:])):
        raise ValueError("Mixture-level TGA intervals must not overlap")
    if sum(row.loss_fraction for row in tga) >= 1:
        raise ValueError("Total TGA loss must be < 100% of the initial dry sample")
    if len({x.name for x in tga}) != len(tga):
        raise ValueError("TGA interval names must be unique")
    settings_data = _object(p["settings"], ThermalActivationSettings, "settings")
    if {"activation_temperature_C", "holding_time_h"} & set(settings_data):
        raise ValueError("Supply activation_temperature_C and holding_time_h as top-level process parameters")
    settings = ThermalActivationSettings(
        activation_temperature_C=p["activation_temperature_C"], holding_time_h=p["holding_time_h"], **settings_data)
    for key, value in asdict(settings).items():
        _number(value, f"settings.{key}", -273.15 if key.endswith("temperature_C") else 0.0)
    scenario_data = _object(p["scenario"], StandardizedScenario, "scenario")
    scenario = StandardizedScenario(**scenario_data)
    for key, value in asdict(scenario).items():
        if key != "name" and value is not None:
            _number(value, f"scenario.{key}", -273.15 if key == "gas_exit_temperature_C" else 0.0)
    if not isinstance(scenario.name, str):
        raise ValueError("scenario.name must be a string")
    if scenario.lambda_heatup < 1:
        raise ValueError("lambda_heatup must be >= 1")
    if not isinstance(p["reaction_terms"], list):
        raise ValueError("reaction_terms must be a list")
    explicit_reactions = []
    for row in p["reaction_terms"]:
        values = _object(row, ReactionTerm, "reaction term")
        for key, value in values.items():
            if key != "name":
                _number(value, f"reaction.{key}")
        term = ReactionTerm(**values)
        if not isinstance(term.name, str) or not term.name.strip() or term.mass_fraction_in_feed > 1:
            raise ValueError("Reaction term requires a name and mass_fraction_in_feed <= 1")
        explicit_reactions.append(term)
    if len({x.name for x in explicit_reactions}) != len(explicit_reactions):
        raise ValueError("Reaction term names must be unique")
    # An authored case may already contain mineral-specific reaction terms.
    # Those take precedence over TGA-derived reference terms, never add both.
    reactions = explicit_reactions or reference_reactions
    reaction_heat_basis = "explicit" if explicit_reactions else "tga_reference" if reference_reactions else "excluded"
    if explicit_reactions and reference_reactions:
        params.warnings.append("Explicit reaction_terms take precedence; automatic reference enthalpies were not added again")
    if not reactions:
        params.warnings.append("No reaction enthalpy is available: choose an isolated pure-reaction TGA interval or provide explicit reaction_terms")
    model = GeneralThermalActivationProcess(FeedComposition(feed), tga, settings, scenario, reactions)
    report = model.full_report()
    inv = report["inventory"]
    report["effective_settings"] = asdict(settings)
    report["effective_scenario"] = asdict(scenario)
    report["tga_basis"] = p["tga_basis"]
    report["thermal_model"] = f"Q = {scenario.lambda_heatup:g} × Q_min + Q_hold; no additional product cooling loss"
    report["feed_assignment"] = {
        "mode": "single_upstream_material" if automatic_feed else "explicit_recipe",
        "reference_recipe_kg": feed,
        "note": "Recipe masses define relative shares only. Actual input mass follows TGA yield and final-product demand.",
    }
    report["selected_tga_reactions"] = selected_reactions
    report["reaction_heat_basis"] = reaction_heat_basis
    report["effective_reaction_terms"] = [asdict(term) for term in reactions]
    report["factory_use"] = {
        "coefficient_unit_per_kg_product_h": settings.thermal_factory_unit_per_kg_product_h,
        "holding_time_h": settings.holding_time_h,
        "unit_per_kg_product": settings.thermal_factory_unit_per_kg_product_h * settings.holding_time_h,
        "basis": "per kg dry process product; coefficient multiplied by holding time",
        "source_reference": (params.provenance["settings"].get("source_note") or "Explicit settings override"
                             if "thermal_factory_unit_per_kg_product_h" in settings_data else THERMAL_FACTORY_SOURCE),
        "coefficient_origin": ("provided" if "thermal_factory_unit_per_kg_product_h" in settings_data
                               else "supporting_data_default"),
    }
    if selected_reactions:
        params.warnings.append("TGA reaction intervals use case-assumed temperature windows, not universal thresholds; reference heat is included automatically for listed pure reactions")
    params.warnings.append("Thermal defaults are in effective_settings/effective_scenario; heat demand has no assigned energy supply")
    chain_compatible = len([mass for mass in feed.values() if mass > 0]) == 1
    if not chain_compatible:
        params.warnings.append("Multi-component feed calculated locally; chain linking requires component-to-upstream mapping")
    result = calculated_result(
        process_input, params,
        {"upstream_input_kg": model.feed_required_per_kg_product(),
         "heat_kwh": inv["standardized_heat_kWh_per_kg_product"],
         "thermal_factory_unit": report["factory_use"]["unit_per_kg_product"],
         "co2_emitted_kg": inv["CO2_to_air_kg_per_kg_product"],
         "water_to_air_kg": inv["H2O_to_air_kg_per_kg_product"]},
        report, source_file="src/calculation/models/thermal_activation.py",
        energy_kind="heat", chain_compatible=chain_compatible,
    )
    # The retained thermal model computes directly on a product basis. Keep
    # that native basis; do not back-calculate fictitious pre-normalized data.
    native_inventory = {key: result.metadata["inventory"][key] for key in (
        "upstream_input_kg", "heat_kwh", "co2_emitted_kg", "water_to_air_kg", "thermal_factory_unit")}
    result.metadata["recording"] = {
        "native_basis": "per kg dry process product", "native_inventory": native_inventory,
        "normalization_factor_to_process_product": 1.0,
        "normalization_note": "The retained model already uses TGA-derived yield to calculate product-basis quantities; details.tga_yield records that conversion.",
        "exchange_metadata": {
            key: {
                "generation_layer": "L1", "source_reference": "src/calculation/models/thermal_activation.py:GeneralThermalActivationProcess",
                "parameter_codes": (["feed_composition_table", "tga_intervals_table", "tga_basis", "activation_temperature_C",
                                     "holding_time_h", "settings", "scenario", "reaction_terms"]
                                    if key == "heat_kwh" else
                                    ["feed_composition_table", "tga_intervals_table", "tga_basis", "activation_temperature_C"]),
                "role": "exchange", "exchange_type": exchange_type, "unit": unit,
            } for key, exchange_type, unit in (
                ("upstream_input_kg", "technosphere", "kg"),
                ("heat_kwh", "technosphere", "kWh"),
                ("co2_emitted_kg", "elementary", "kg"),
                ("water_to_air_kg", "elementary", "kg"),
            )
        },
    }
    result.metadata["recording"]["exchange_metadata"]["thermal_factory_unit"] = {
        "generation_layer": None,
        "source_reference": report["factory_use"]["source_reference"],
        "parameter_codes": ["holding_time_h", "settings"],
        "role": "exchange", "exchange_type": "technosphere", "unit": "unit",
        "native_basis": "per kg dry process product",
        "native_quantity": report["factory_use"]["unit_per_kg_product"],
        "normalization_factor_to_process_product": 1.0,
    }
    return result
