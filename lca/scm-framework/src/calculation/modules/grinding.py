from ..models.grinding import GrindingModel, grinding_library
from ..parameters import Parameters
from ..process_settings.grinding import GRINDING_SPECS, GrindingParams
from ..supporting_data.infrastructure import GRINDING_MACHINE_SOURCE
from .common import calculated_result, recovery_recording
from .recovery import apply_recovery


def calculate_grinding(process_input):
    params = Parameters(process_input, GRINDING_SPECS)
    p = params.values
    library_record = None
    if p["grinding_library_key"]:
        key = p["grinding_library_key"]
        library_record = grinding_library().get(key)
        if library_record is None:
            raise ValueError(f"Unknown grinding_library_key: {key}")
        owned = ("material_key", "fine_n", "transition_um",
                 "fine_target_um", "fine_anchor_energy_kwh_per_tonne")
        if any(params.provenance[code]["origin"] == "provided" for code in owned):
            raise ValueError("Library allows explicit Wi_value/fine_K overrides, but not simultaneous legacy material/anchor/regime settings")
        resolved = dict(Wi_value=library_record["Wi_kWh_per_tonne"], material_key=key,
                        fine_K=library_record["fine_K"], fine_n=library_record["fine_n"],
                        transition_um=library_record["transition_um"])
        for code, value in resolved.items():
            if code in ("Wi_value", "fine_K") and params.provenance[code]["origin"] == "provided":
                params.provenance[code]["origin"] = "user_override"
                continue
            p[code] = value
            params.provenance[code].update(value=value, origin="background_library", source_note=library_record["source_file"])
        params.warnings = [warning for warning in params.warnings if not warning.startswith("Model defaults used:")]
        defaults = [code for code, record in params.provenance.items() if record["origin"] == "model_default"]
        if defaults:
            params.warnings.append("Model defaults used: " + ", ".join(defaults))
        params.warnings.append(f"Library Wi: {library_record['basis']} (confidence: {library_record['confidence']})")
        if library_record["fine_calibration"]:
            calibration = library_record["fine_calibration"]
            if params.provenance["fine_K"]["origin"] == "background_library":
                params.provenance["fine_K"]["source_note"] = calibration["source_file"] + ": " + calibration["basis"]
            if p["P80_um"] < p["transition_um"]:
                params.warnings.append(calibration["basis"])
        elif p["fine_K"] is None and p["grinding_model"] == "hybrid" and p["P80_um"] < p["transition_um"]:
            raise ValueError(f"No fine K is stored for {key}; hybrid grinding below {p['transition_um']:g} µm needs a validated material-specific calibration")
    wi = p["Wi_value"]
    material = p["material_key"]
    material_metadata = None
    if wi is None:
        if material is None:
            raise ValueError("Grinding requires Wi_value or an explicit material_key")
        material_metadata = GrindingModel.get_material_metadata(material)
        wi = material_metadata["Wi_kWh_per_tonne"]
        params.warnings.append(f"Wi uses the selected material value for {material}: {material_metadata['basis']}")
    fine_k = p["fine_K"]
    anchor, target = p["fine_anchor_energy_kwh_per_tonne"], p["fine_target_um"]
    if (anchor is None) != (target is None):
        raise ValueError("Fine calibration requires both fine_target_um and fine_anchor_energy_kwh_per_tonne")
    if anchor is not None:
        if fine_k is not None:
            raise ValueError("Supply fine_K or an anchor calibration, not both")
        fine_k = GrindingModel.calibrate_fine_K_from_anchor(p["transition_um"], target, anchor, p["fine_n"])
    model_params = GrindingParams(
        material_name=material or "custom", Wi_value=wi,
        transition_um=p["transition_um"], fine_K=fine_k, fine_n=p["fine_n"],
        material_factor=p["material_factor"], auxiliaries_factor=p["auxiliaries_factor"],
    )
    if p["grinding_model"] == "bond":
        energy = GrindingModel.bond_specific_energy_kwh_per_tonne(p["F80_um"], p["P80_um"], wi)
        energy *= p["material_factor"] * p["auxiliaries_factor"]
        if p["P80_um"] < p["transition_um"]:
            params.warnings.append("Explicit Bond-only extrapolation below the fine-grinding transition")
    else:
        energy = GrindingModel.hybrid_grinding_energy_kwh_per_tonne(p["F80_um"], p["P80_um"], model_params)
    input_machine_key = "grinding_machine_kg_per_kg_processed"
    product_machine_key = "grinding_machine_kg_per_kg_product"
    if p[input_machine_key] is not None:
        if params.provenance[product_machine_key]["origin"] == "provided":
            raise ValueError("Supply one grinding equipment basis: per kg product or per kg processed input")
        machine_key, machine_basis = input_machine_key, "per kg processed input"
        # An explicit saved input-basis coefficient keeps its original meaning.
        # The new product-basis default is inactive for this calculation.
        p[product_machine_key] = None
        params.provenance[product_machine_key].update(value=None, origin="not_used")
        params.warnings = [warning for warning in params.warnings if not warning.startswith("Model defaults used:")]
        defaults = [code for code, record in params.provenance.items() if record["origin"] == "model_default"]
        if defaults:
            params.warnings.append("Model defaults used: " + ", ".join(defaults))
    else:
        machine_key, machine_basis = product_machine_key, "per kg dry process product"
        if params.provenance[machine_key]["origin"] == "model_default":
            params.provenance[machine_key]["source_note"] = GRINDING_MACHINE_SOURCE
    machine = p[machine_key]
    details = {"grinding_model": p["grinding_model"], "Wi_kWh_per_tonne": wi,
         "fine_K": fine_k, "material_proxy": material_metadata, "input_library": library_record,
         "electricity_activity_name": p["electricity_activity_name"],
         "unit_electricity_kwh": energy / 1000.0}
    inventory = apply_recovery(params, {"electricity_kwh": energy / 1000.0}, details)
    # Equipment uses its own declared denominator, independent of the energy
    # inventory basis. The SI product-basis default must not acquire 1/yield.
    machine_scale = inventory["upstream_input_kg"] if machine_key == input_machine_key else 1.0
    inventory["grinding_machine_kg"] = machine * machine_scale
    details["grinding_equipment"] = {"parameter_code": machine_key,
        "coefficient": machine, "basis": machine_basis,
        "normalization_factor_to_process_product": machine_scale}
    result = calculated_result(
        process_input, params, inventory, details,
        source_file="../Cycle2/Processes.py",
    )
    result.metadata["allocation_factor"] = details["recovery"]["allocation_factor"]
    result.metadata["recording"] = recovery_recording(
        params, {"electricity_kwh": energy / 1000.0}, inventory, details,
        {"electricity_kwh": {
            "generation_layer": "L1", "source_reference": "src/calculation/models/grinding.py:GrindingModel",
            "parameter_codes": ["F80_um", "P80_um", "Wi_value", "material_key", "grinding_library_key",
                                "grinding_model", "transition_um", "fine_K", "fine_n", "fine_target_um",
                                "fine_anchor_energy_kwh_per_tonne", "material_factor", "auxiliaries_factor"],
            "role": "exchange", "exchange_type": "technosphere", "unit": "kWh",
        }, "grinding_machine_kg": {
            "generation_layer": None,
            "source_reference": (params.provenance[machine_key].get("source_note")
                                 or f"{machine_key} parameter; original coefficient source not supplied"),
            "parameter_codes": ([machine_key, "yield_fraction"] if machine_key == input_machine_key else [machine_key]),
            "role": "exchange", "exchange_type": "technosphere", "unit": "kg",
            "native_basis": machine_basis, "native_quantity": machine,
            "normalization_factor_to_process_product": machine_scale,
            "note": "Equipment-use coefficient applied on its declared mass basis; its L2/L3 derivation is not inferred from the supplier name.",
        }},
    )
    return result
