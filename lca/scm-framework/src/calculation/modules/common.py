from __future__ import annotations

from src.calculation.schemas import CalculationItem


def recovery_recording(parameters, native_inventory, inventory, details, exchange_metadata):
    """Record the existing recovery calculation without changing its quantities.

    Unit burdens use the selected input/output basis. The recovery mass balance
    is calculated directly per kg target output, so those rows have their own
    basis rather than being scaled a second time.
    """
    recovery = details["recovery"]
    basis = ("per kg processed input" if recovery["inventory_basis"] == "processed_input"
             else "per kg dry process product")
    metadata = dict(exchange_metadata)
    mass_parameters = (["input_mass_kg", "output_mass_kg"]
                       if "input_mass_kg" in parameters.values else ["yield_fraction"])
    for key, exchange_type, note in (
        ("upstream_input_kg", "technosphere", "Required upstream material; provider is resolved at route assembly."),
        ("solid_loss_kg", "unclassified", "Physical rejected material; no waste-treatment provider is selected here."),
        ("coproduct_kg", "production", "Physical coproduct output; allocation does not change its mass."),
    ):
        metadata[key] = {
            "generation_layer": "L1", "source_reference": "src/calculation/modules/recovery.py:apply_recovery",
            "parameter_codes": mass_parameters + ["coproduct_fraction"],
            "role": "exchange", "exchange_type": exchange_type, "unit": "kg",
            "native_basis": "per kg dry process product", "native_quantity": inventory[key],
            "normalization_factor_to_process_product": 1.0, "note": note,
        }
    return {
        "native_basis": basis, "native_inventory": dict(native_inventory),
        "normalization_factor_to_process_product": recovery["inventory_scale"],
        "exchange_metadata": metadata,
        "normalization_note": "Physical quantities are unallocated. Allocation factors are recorded separately from mass normalization.",
    }


def calculated_result(process_input, parameters, inventory, details, *, source_file, energy_kind="electricity", chain_compatible=True):
    """Every inventory quantity is per kg dry output from this process."""
    from math import isfinite

    quantities = {
        "upstream_input_kg": 1.0, "electricity_kwh": 0.0, "heat_kwh": 0.0,
        "water_input_kg": 0.0, "wastewater_treatment_kg": 0.0,
        "wastewater_release_kg": 0.0, "co2_stored_kg": 0.0,
        "co2_emitted_kg": 0.0, "water_to_air_kg": 0.0, "solid_loss_kg": 0.0,
        **inventory,
    }
    if any(not isfinite(value) or value < 0 for value in quantities.values()):
        raise ValueError("Calculated inventory must contain finite nonnegative quantities")
    return CalculationItem(
        process_name=process_input.process_name, process_order=process_input.process_order,
        result_code=f"{energy_kind}_kwh_per_kg_product",
        value=str(quantities[f"{energy_kind}_kwh"]), unit="kWh/kg dry process product",
        metadata={
            "status": "calculated",
            "source_file": source_file, "basis": "per_kg_dry_process_product",
            "inventory": quantities, "details": details,
            "parameters": parameters.provenance, "warnings": parameters.warnings,
            "chain_compatible": chain_compatible,
        },
    )
