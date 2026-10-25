"""Equipment-use coefficients from the user-supplied SI inventory tables.

All coefficients below use dry product mass as the denominator. Factory use
also scales with the duration of the corresponding operation in hours.
"""

GRINDING_MACHINE_KG_PER_KG_PRODUCT = 4.41e-7
THERMAL_FACTORY_UNIT_PER_KG_PRODUCT_H = 4.029e-14
CARBONATION_FACTORY_UNIT_PER_KG_PRODUCT_H = 4.029e-13

GRINDING_MACHINE_SOURCE = "SI1-3_ParameterAndInventories.xlsx, S1.1 Pysical, F20"
THERMAL_FACTORY_SOURCE = "SI1-3_ParameterAndInventories.xlsx, S1.2 Thermal activation, E57-F58"
CARBONATION_FACTORY_SOURCE = "SI1-3_ParameterAndInventories.xlsx, S1.3 Carbonation, E108-F109"
