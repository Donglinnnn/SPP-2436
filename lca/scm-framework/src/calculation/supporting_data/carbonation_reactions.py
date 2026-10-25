"""Carbonation reaction heat references, including derived screening proxies."""

from typing import Any, Dict


# Positive magnitudes of exothermic carbonation reaction heat, normalized per
# mol CO2 taken up. These are screening/proxy values; case builders can always
# override them with an explicit `reaction_heat_kj_per_mol_co2`.
REACTION_HEAT_LIBRARY_KJ_PER_MOL_CO2: Dict[str, Dict[str, Any]] = {
    "cao_to_calcite": {
        "reaction_heat_kj_per_mol_co2": 178.3,
        "reaction": "CaO + CO2 -> CaCO3",
        "note": "Free lime carbonation proxy.",
    },
    "portlandite_to_calcite": {
        "reaction_heat_kj_per_mol_co2": 113.7,
        "reaction": "Ca(OH)2 + CO2 -> CaCO3 + H2O",
        "note": "Portlandite carbonation proxy.",
    },
    "c2s_to_calcite_silicic_acid": {
        "reaction_heat_kj_per_mol_co2": 203.5,
        "reaction": "Ca2SiO4 + 2CO2 + 2H2O -> 2CaCO3 + H4SiO4",
        "note": "Dicalcium silicate proxy used by Li et al. 2023.",
    },
    "c3s_to_calcite_silicic_acid": {
        "reaction_heat_kj_per_mol_co2": 195.1,
        "reaction": "Ca3SiO5 + 3CO2 + 2H2O -> 3CaCO3 + H4SiO4",
        "provenance_tag": "DER/LIT",
        "note": (
            "Tricalcium silicate proxy. Derived as "
            "(2*C2S carbonation heat + CaO carbonation heat)/3 mol CO2."
        ),
        "source_note": (
            "Derived proxy from Li et al. 2023 C2S carbonation heat and "
            "the CaO-to-calcite reaction heat used in this library."
        ),
    },
    "csh_to_calcite_silica_gel": {
        "reaction_heat_kj_per_mol_co2": 218.6,
        "reaction": (
            "3CaO.2SiO2.4H2O + 3CO2 -> "
            "3CaCO3 + 2SiO2(am) + 4H2O"
        ),
        "provenance_tag": "DER/LIT",
        "note": (
            "Stoichiometric C-S-H proxy based on C3S2H4. Derived by Hess cycle "
            "from C3S carbonation, C3S hydration heat, and portlandite carbonation."
        ),
        "source_note": (
            "C-S-H composition is variable; this is a C3S2H4 proxy informed by "
            "Richardson 2008 and C-S-H(I) carbonation studies by Garbev/Black et al. "
            "The heat value is derived, not directly measured."
        ),
    },
}
