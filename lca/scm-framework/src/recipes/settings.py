"""Recipe defaults shared by calculation and the browser schema.

Conversion assumptions are separate from the initial form recipe. Starter
ingredient quantities are never supplied implicitly to a calculation.
"""

from types import MappingProxyType

DEFAULT_DENSITIES_KG_PER_M3 = {
    'cement': 3150, 'sand': 2650, 'aggregate': 2650,
    'recycled_fine': 2400, 'recycled_coarse': 2400, 'water': 1000,
}

FOAM_REFERENCE_MASS_KG = 1000  # User's provisional interpretation; source basis is disputed.
FOAM_MACHINE_KG_PER_UNIT = 2000  # Ratio of 1.46e-3 kg to 7.30e-7 unit; independently unverified.

DEFAULTS = MappingProxyType({
    'basis': 'per_m3',
    'volume_mode': 'absolute',
    'air_percent': 0,
    'recycled_yield_fraction': 1,
    'preparation_mode': 'mixing',
    'foam_reference_mass_kg': FOAM_REFERENCE_MASS_KG,
    'foam_machine_kg_per_unit': FOAM_MACHINE_KG_PER_UNIT,
})

# Initial browser inputs, not material properties or a reference concrete.
FORM_DEFAULTS = MappingProxyType({
    'name': 'My mixture',
    'specimen_class': 'paste',
})
STARTER_AMOUNTS_KG = MappingProxyType({
    'cement': 700, 'scm': 0, 'sand': 0, 'aggregate': 0,
    'recycled_fine': 0, 'recycled_coarse': 0, 'water': 350,
})


def recipe_input_defaults():
    """Return independent copies for API clients."""
    return {
        'default_densities': dict(DEFAULT_DENSITIES_KG_PER_M3),
        'input_defaults': dict(DEFAULTS),
        'form_defaults': {**FORM_DEFAULTS, 'amounts': dict(STARTER_AMOUNTS_KG)},
    }
