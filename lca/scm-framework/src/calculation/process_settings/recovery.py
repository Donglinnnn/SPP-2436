"""Shared yield, coproduct allocation and inventory-basis input fields."""

from ..parameters import number, text_spec


def recovery_specs(*, with_yield=False, basis="processed_input"):
    specs = {
        "coproduct_fraction": number("fraction", default=0.0, maximum=1.0, conversions={"%": 0.01},
            description="Fraction of non-target dry output recovered as coproduct; remainder is waste. Not a second yield."),
        "allocation_method": text_spec(default="none", choices=("none", "mass"),
            description="Mass allocation affects attributed burdens, never the physical mass flow."),
        "inventory_basis": text_spec(default=basis, choices=("processed_input", "target_output"),
            description="Whether unit inventory is per kg processed material or per kg recovered target product."),
    }
    if with_yield:
        specs["yield_fraction"] = number("fraction", default=1.0, exclusive_minimum=True, maximum=1.0,
            conversions={"%": 0.01}, description="Target dry output / dry input. Do not repeat a downstream separation yield.")
    return specs
