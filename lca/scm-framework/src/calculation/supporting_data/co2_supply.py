"""Assumptions for the optional captured/liquefied CO2 energy helper.

These values are not the active web C0/C1/C2 supply inventories. Those inventories
are resolved separately in recipes; this helper is used only when explicitly
called and must not be added to an already accounted CO2 supply pathway.
"""

# Captured/liquefied CO2 supply scenario parameters. These are not used by the
# baseline route-adaptive model unless a case builder explicitly calls the
# helper function.
CAPTURED_CO2_MINERALIZATION_PLANT_KWH_PER_KG = 0.000133
CAPTURED_CO2_SUPPLY_KWH_PER_KG_CO2 = 0.276
