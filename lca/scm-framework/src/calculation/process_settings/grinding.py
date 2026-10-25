"""Grinding input contract and editable calculation settings."""

from dataclasses import dataclass
from math import isfinite
from typing import Optional

from ..parameters import SIZE, number, text_spec
from ..units import SHORT_TON_TO_TONNE
from .grinding_defaults import DEFAULTS, REFERENCE_PRODUCT, WORK_INDEX_UNIT
from .recovery import recovery_specs


@dataclass
class GrindingParams:
    """Resolved material and equipment assumptions supplied to the equations."""

    material_name: str
    Wi_value: float
    Wi_unit: str = WORK_INDEX_UNIT
    transition_um: float = DEFAULTS["transition_um"]
    fine_K: Optional[float] = None
    fine_n: Optional[float] = DEFAULTS["fine_n"]
    material_factor: float = DEFAULTS["material_factor"]
    auxiliaries_factor: float = DEFAULTS["auxiliaries_factor"]
    reference_product: str = REFERENCE_PRODUCT
    comment: str = ""

    def __post_init__(self):
        if (isinstance(self.Wi_value, bool)
                or not isinstance(self.Wi_value, (int, float))
                or not isfinite(self.Wi_value) or self.Wi_value <= 0):
            raise ValueError("Wi_value must be an explicit finite positive number")

    def Wi_kWh_per_tonne(self) -> float:
        if self.Wi_unit == "kWh_per_tonne":
            return self.Wi_value
        if self.Wi_unit == "kWh_per_short_ton":
            return self.Wi_value / SHORT_TON_TO_TONNE
        raise ValueError(
            f"Unsupported Wi_unit '{self.Wi_unit}'. "
            "Use 'kWh_per_tonne' or 'kWh_per_short_ton'."
        )


GRINDING_SPECS = {
    **recovery_specs(with_yield=True),
    "grinding_library_key": text_spec(description="Select material/case defaults; explicit Wi_value and fine_K override them. Omit for custom or legacy parameters."),
    "F80_um": number("um", required=True, exclusive_minimum=True, conversions=SIZE),
    "P80_um": number("um", required=True, exclusive_minimum=True, conversions=SIZE),
    "Wi_value": number("kWh/t", exclusive_minimum=True, conversions={
        "kWh_per_tonne": 1.0, "kWh/short ton": 1 / SHORT_TON_TO_TONNE,
        "kWh_per_short_ton": 1 / SHORT_TON_TO_TONNE,
    }, description="Required unless a listed material supplies its Bond work index."),
    "material_key": text_spec(),
    "grinding_model": text_spec(default=DEFAULTS["grinding_model"], choices=("hybrid", "bond")),
    "transition_um": number("um", default=DEFAULTS["transition_um"], exclusive_minimum=True, conversions=SIZE),
    "fine_K": number("kWh·µm/t", exclusive_minimum=True),
    "grinding_machine_kg_per_kg_product": number("kg/kg",
        default=DEFAULTS["grinding_machine_kg_per_kg_product"],
        description="Grinding equipment per kg dry product. Do not also supply the processed-input coefficient."),
    "grinding_machine_kg_per_kg_processed": number("kg/kg",
        description="Optional legacy equipment coefficient per kg processed input; overrides the product-basis default."),
    "fine_n": number(default=DEFAULTS["fine_n"], minimum=1.0),
    "fine_target_um": number("um", exclusive_minimum=True, conversions=SIZE),
    "fine_anchor_energy_kwh_per_tonne": number("kWh/t", exclusive_minimum=True),
    "material_factor": number("fraction", default=DEFAULTS["material_factor"], exclusive_minimum=True),
    "auxiliaries_factor": number("fraction", default=DEFAULTS["auxiliaries_factor"], exclusive_minimum=True),
    "electricity_activity_name": text_spec(unit="activity name",
        description="Recorded only; no background dataset is resolved by this calculation."),
}
