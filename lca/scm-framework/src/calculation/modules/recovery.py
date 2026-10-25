"""Keep physical yields separate from allocation of foreground burdens."""


def apply_recovery(params, inventory, details, *, separation=False):
    p = params.values
    if separation:
        feed, product = p["input_mass_kg"], p["output_mass_kg"]
        if product > feed:
            raise ValueError("Output mass must not exceed input mass for sieving/sorting/screening")
        yield_fraction = product / feed
        details.update(input_mass_kg=feed, output_mass_kg=product)
    else:
        yield_fraction = p["yield_fraction"]
    upstream = 1 / yield_fraction
    others = upstream - 1
    coproduct = others * p["coproduct_fraction"]
    factor = 1 / (1 + coproduct) if p["allocation_method"] == "mass" else 1.0
    # Unit inventories remain identifiable; convert once to physical inventory
    # per kg target product, never put an allocation factor in the mass ratio.
    scale = upstream if p["inventory_basis"] == "processed_input" else 1.0
    physical = {key: value * scale for key, value in inventory.items()}
    physical.update(upstream_input_kg=upstream, solid_loss_kg=others-coproduct, coproduct_kg=coproduct)
    details["recovery"] = dict(yield_fraction=yield_fraction, inventory_basis=p["inventory_basis"],
        inventory_scale=scale, coproduct_fraction=p["coproduct_fraction"],
        allocation_method=p["allocation_method"], allocation_factor=factor,
        note="Allocation applies to this step and its upstream burdens; physical flows remain unallocated.")
    if others:
        params.warnings.append("Record each yield loss only once. Coproducts and waste are physical outputs; reject treatment is not included.")
    if coproduct and p["allocation_method"] == "none":
        params.warnings.append("Coproduct is recorded but all burdens are attributed to the target product (no allocation).")
    return physical
