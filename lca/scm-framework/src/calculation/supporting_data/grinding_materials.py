"""Grinding reference values and optional, explicitly sourced calibration anchors.

Material proxies and case anchors retain their original provenance. Selecting a
record does not make its value a universal material property.
"""
from typing import Any, Dict


MATERIAL_WIFI_LIBRARY: Dict[str, Dict[str, Any]] = {
    "dolomite": {
        "Wi_kWh_per_tonne": 11.27,
        "confidence": "high",
        "basis": "Wills & Finch table",
    },
    "steel_slag": {
        "Wi_kWh_per_tonne": 21.94,
        "Wi_range_kWh_per_tonne": (15.21, 27.45),
        "confidence": "medium",
        "basis": "average of BOF/EAF/LMF slags from Bond study",
    },
    "clay": {
        "Wi_kWh_per_tonne": 10.38,
        "confidence": "medium",
        "basis": "kaolin Bond test used as proxy for kaolinite-rich clay",
    },
    "coal_mining_dumps": {
        "Wi_kWh_per_tonne": 10.38,
        "confidence": "low",
        "basis": "proxy from kaolinite-rich clay; suitable for gangue-rich dumps",
    },
    "coal_mining_dumps_carbon_rich": {
        "Wi_kWh_per_tonne": 13.00,
        "confidence": "medium",
        "basis": "proxy from coal in Wills & Finch",
    },
    "recycled_cement_paste": {
        "Wi_kWh_per_tonne": 13.60,
        "confidence": "low",
        "basis": "proxy inferred from clinker/limestone Bond indices in cement materials study",
    },
    "bio_feedstocks_ash": {
        "Wi_kWh_per_tonne": 22.40,
        "confidence": "medium_high",
        "basis": "direct SCBA Bond-type value reported from grinding study",
    },
}

FINE_ANCHORS = {
    "steel_slag": {
        "target_um": 19.0, "energy_kwh_per_tonne": 36.7,
        "source_file": "../Cycle2/P6_Steel_slag.py",
        "basis": "P6 steel-slag case calibration (Mahoutian et al., 2018 anchor)",
    },
    "recycled_cement_paste": {
        "target_um": 63.0, "energy_kwh_per_tonne": 12.0,
        "source_file": "../Cycle2/P7_re_SEM.py",
        "basis": "P7 RCP case assumption; tune with measured data, not a universal measured K",
    },
}
