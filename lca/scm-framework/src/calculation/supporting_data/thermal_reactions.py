"""TGA reaction labels and author-adopted reference enthalpies.

Preset windows are case assumptions, not universal reaction temperatures. Heat
is included automatically only when an interval assigns all its gas loss to a
listed pure reaction with a reference enthalpy. Descriptive rows have no heat.
"""
from copy import deepcopy


THERMAL_REACTIONS = {
    "portlandite_dehydroxylation_v1": {
        "label": "Ca(OH)₂ dehydroxylation", "equation": "Ca(OH)₂ → CaO + H₂O",
        "kind": "chemical_reaction", "start_C": 400.0, "end_C": 550.0,
        "h2o_share": 1.0, "co2_share": 0.0,
        "reference_enthalpy_kj_per_kg_reactant": 1486.0,
        "reactant_molar_mass_g_per_mol": 74.0927, "gas_molar_mass_g_per_mol": 18.0153,
        "enthalpy_source": "Author-adopted PROP/LIT reference table; full citation pending",
        "source_file": "../Cycle2/P1_RCP_Carbon.py",
        "note": "P1 case window. Assign only an isolated portlandite H₂O loss; broad water loss is not pure portlandite.",
    },
    "calcite_decarbonation_v1": {
        "label": "CaCO₃ decomposition", "equation": "CaCO₃ → CaO + CO₂",
        "kind": "chemical_reaction", "start_C": 550.0, "end_C": 900.0,
        "h2o_share": 0.0, "co2_share": 1.0,
        "reference_enthalpy_kj_per_kg_reactant": 1790.0,
        "reactant_molar_mass_g_per_mol": 100.0869, "gas_molar_mass_g_per_mol": 44.0095,
        "enthalpy_source": "Author-adopted PROP/LIT reference table; full citation pending",
        "source_file": "../Cycle2/P1_RCP_Carbon.py",
        "note": "P1 case window. Assign only an isolated calcite CO₂ loss.",
    },
    "brucite_dehydroxylation_v1": {
        "label": "Mg(OH)₂ dehydroxylation", "equation": "Mg(OH)₂ → MgO + H₂O",
        "kind": "chemical_reaction", "start_C": None, "end_C": None,
        "h2o_share": 1.0, "co2_share": 0.0,
        "reference_enthalpy_kj_per_kg_reactant": 1399.0,
        "reactant_molar_mass_g_per_mol": 58.3197, "gas_molar_mass_g_per_mol": 18.0153,
        "enthalpy_source": "Author-adopted PROP/LIT reference table; full citation pending",
        "note": "Enter a measured interval. Assign only an isolated brucite H₂O loss.",
    },
    "magnesite_decarbonation_v1": {
        "label": "MgCO₃ decomposition", "equation": "MgCO₃ → MgO + CO₂",
        "kind": "chemical_reaction", "start_C": None, "end_C": None,
        "h2o_share": 0.0, "co2_share": 1.0,
        "reference_enthalpy_kj_per_kg_reactant": 1387.0,
        "reactant_molar_mass_g_per_mol": 84.3139, "gas_molar_mass_g_per_mol": 44.0095,
        "enthalpy_source": "Author-adopted PROP/LIT reference table; full citation pending",
        "note": "Enter a measured interval. Assign only an isolated magnesite CO₂ loss.",
    },
    "free_water_release_v1": {
        "label": "Free-water evaporation", "equation": "H₂O(l) → H₂O(g)",
        "kind": "physical_process", "start_C": 30.0, "end_C": 105.0,
        "h2o_share": 1.0, "co2_share": 0.0,
        "source_file": "../Cycle2/P1_RCP_Carbon.py",
        "note": "P1 low-temperature H₂O-loss interval; phase change, not a decomposition reaction.",
    },
    "bound_water_release_v1": {
        "label": "Bound-water release · descriptive", "equation": "Hydrated phases → dehydrated phases + H₂O",
        "kind": "process_description", "start_C": 105.0, "end_C": 400.0,
        "h2o_share": 1.0, "co2_share": 0.0,
        "source_file": "../Cycle2/P1_RCP_Carbon.py",
        "note": "Describes the retained P1 H₂O-loss interval; not a balanced mineral-specific equation.",
    },
    "clay_dehydroxylation_v1": {
        "label": "Clay / illite dehydroxylation · descriptive", "equation": "Hydroxylated clay → dehydroxylated clay + H₂O",
        "kind": "process_description", "start_C": 200.0, "end_C": 700.0,
        "h2o_share": 1.0, "co2_share": 0.0,
        "source_file": "../Cycle2/P10_activatedClay_illite.py",
        "note": "Retained broad illite-case window; no unique mineral formula or reaction enthalpy inferred.",
    },
    "carbonate_loss_v1": {
        "label": "Carbonate CO₂ loss · descriptive", "equation": "Carbonate-bearing phases → solid products + CO₂",
        "kind": "process_description", "start_C": 700.0, "end_C": 900.0,
        "h2o_share": 0.0, "co2_share": 1.0,
        "source_file": "../Cycle2/P10_activatedClay_illite.py",
        "note": "Retained illite-case carbonate-loss window; does not identify a specific carbonate mineral.",
    },
}


def thermal_reaction_library():
    return deepcopy(THERMAL_REACTIONS)
