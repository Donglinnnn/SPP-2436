"""User-supplied foam-mixing inventory quantities per reference batch.

The reference mass and machine unit-to-mass conversion are provisional editable
assumptions in recipes/settings.py. Ordinary paste, mortar and concrete use the
separately configured mixing inventory resolved by background.preparation().
"""

FOAM_ELECTRICITY_KWH = 0.41
FOAM_MACHINE_UNIT = 7.30e-7
