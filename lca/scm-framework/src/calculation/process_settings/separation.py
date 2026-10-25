"""Shared input contract for sieving, sorting and retained screening."""

from ..parameters import number, text_spec
from .recovery import recovery_specs


def separation_specs(name):
    inventory_id = f"cycle2-{name.lower()}-v1"
    return {
        **recovery_specs(basis="processed_input" if name == "Screening" else "target_output"),
        "inventory_id": text_spec(default=inventory_id, choices=(inventory_id,)),
        "input_mass_kg": number("kg", required=True, exclusive_minimum=True, conversions={"g": 0.001, "t": 1000.0}),
        "output_mass_kg": number("kg", required=True, exclusive_minimum=True, conversions={"g": 0.001, "t": 1000.0}),
    }


SIEVING_SPECS = separation_specs("Sieving")
SORTING_SPECS = separation_specs("Sorting")
SCREENING_SPECS = separation_specs("Screening")
