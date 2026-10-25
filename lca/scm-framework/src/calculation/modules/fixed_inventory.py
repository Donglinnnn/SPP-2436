"""Apply retained inventories and explicit separation feed/product ratios."""
from ..supporting_data.operation_inventories import fixed_inventory
from ..parameters import Parameters
from .common import calculated_result, recovery_recording
from .recovery import apply_recovery


def calculate_fixed_inventory(process_input, specs, *, separation=False):
    params = Parameters(process_input, specs)
    library = fixed_inventory(process_input.process_name)
    inventory = {row["code"]: row["value"] for row in library["exchanges"]}
    details = {"input_library": library}
    inventory = apply_recovery(params, inventory, details, separation=separation)
    if params.values["inventory_id"] != library["id"]:
        params.warnings.append("Crushing migrated to user-confirmed 2026-09-22 inventory: 0.00507 MJ diesel combustion + 0.0007 kg water; old diesel-market and equipment inputs are not added.")
    params.provenance["inventory_id"].update(value=library["id"], origin="background_library", source_note=library["source_function"])
    result = calculated_result(process_input, params, inventory, details, source_file=library["source_file"])
    result.metadata["inventory_version"] = library["version"]
    result.metadata["allocation_factor"] = details["recovery"]["allocation_factor"]
    result.metadata["recording"] = recovery_recording(
        params, {row["code"]: row["value"] for row in library["exchanges"]}, inventory, details,
        {row["code"]: {
            "generation_layer": None,
            "source_reference": library["source_file"] + "; " + library["source_function"],
            "parameter_codes": ["inventory_id", "inventory_basis"],
            "role": "exchange", "exchange_type": "technosphere", "unit": row["unit"],
            "note": "Retained fixed inventory: the stored source does not establish whether the quantity was acquired through L2 or L3.",
        } for row in library["exchanges"]},
    )
    return result
