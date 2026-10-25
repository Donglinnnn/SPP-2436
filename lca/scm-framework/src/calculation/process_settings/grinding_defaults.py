"""Editable grinding assumptions shared by the website and Python entry points.

The Bond work index must come from an explicit input or a selected material
record. Fine-grinding coefficients are calculated from sourced anchors using
the transition and exponent below, so their reported calibration basis agrees
with the equation settings.
"""
from types import MappingProxyType

from ..supporting_data.infrastructure import GRINDING_MACHINE_KG_PER_KG_PRODUCT


DEFAULTS = MappingProxyType({
    "grinding_model": "hybrid",
    "transition_um": 100.0,
    "fine_n": 2.0,
    "material_factor": 1.0,
    "auxiliaries_factor": 1.15,
    "grinding_machine_kg_per_kg_product": GRINDING_MACHINE_KG_PER_KG_PRODUCT,
})

WORK_INDEX_UNIT = "kWh_per_tonne"
REFERENCE_PRODUCT = "ground material"
