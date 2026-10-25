"""Backward dry reference-flow propagation for a serial, single-feed chain."""
from math import isfinite


def summarize_chain(items, final_product_kg):
    required_output = final_product_kg
    totals = {}
    allocated_totals = {}
    downstream_allocation = 1.0
    steps = []
    for item in reversed(items):
        inventory = item.metadata["inventory"]
        contributions = {
            key: value * required_output for key, value in inventory.items()
            if key != "upstream_input_kg"
        }
        upstream = inventory["upstream_input_kg"] * required_output
        local_allocation = item.metadata.get("allocation_factor", 1.0)
        if not isfinite(local_allocation) or not 0 < local_allocation <= 1:
            raise ValueError("Allocation factor must be finite and in (0, 1]")
        burden_factor = downstream_allocation * local_allocation
        allocated = {key: value * burden_factor for key, value in contributions.items()}
        if not isfinite(upstream) or any(not isfinite(x) for x in contributions.values()):
            raise ValueError("Reference-flow scaling overflow; reduce functional_unit_kg or check yields")
        steps.append({
            "process_name": item.process_name, "process_order": item.process_order,
            "required_output_kg": required_output, "required_input_kg": upstream,
            "contributions": contributions,
            "allocated_contributions": allocated, "burden_allocation_factor": burden_factor,
        })
        for key, value in contributions.items():
            totals[key] = totals.get(key, 0.0) + value
            allocated_totals[key] = allocated_totals.get(key, 0.0) + allocated[key]
        required_output = upstream
        downstream_allocation = burden_factor
    if any(not isfinite(x) for x in totals.values()):
        raise ValueError("Inventory sum overflow")
    return {
        "status": "complete", "calculation_kind": "foreground_inventory",
        "basis": "requested_final_dry_product", "functional_unit_kg": final_product_kg,
        "initial_feed_required_kg": required_output,
        "totals": totals, "steps": list(reversed(steps)),
        "allocated_totals": allocated_totals,
        "allocation_applied": downstream_allocation < 1.0,
        "allocation_note": "totals and step contributions are physical; allocated_totals and allocated_contributions are target-product shares, not a physical mass balance",
        "boundary": "Selected foreground processes and explicitly listed equipment only; no background LCIA, feedstock burden, upstream CO2-supply burdens or transport",
        "lcia_status": "not_calculated",
    }
