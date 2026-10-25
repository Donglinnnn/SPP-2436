"""Reference material properties used as editable heat-model defaults.

These values retain the existing framework assumptions. Heat capacities are in
kJ/(kg K), and the water latent heat is in kJ/kg. Process settings select these
reference values; route-specific inputs may override them.
"""

CP_SOLID_DEFAULT_KJ_PER_KG_K = 0.90
CP_H2O_STEAM_KJ_PER_KG_K = 2.00
CP_CO2_KJ_PER_KG_K = 1.10
LATENT_HEAT_H2O_KJ_PER_KG = 2257.0
CP_LIQUID_WATER_KJ_PER_KG_K = 4.18
