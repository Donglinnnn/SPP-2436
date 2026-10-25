"""Paper energy sensitivity: each E choice selects electricity and process heat.

E1's electricity factor is the SI S3 delivered German medium-voltage lignite
supply per kWh, including its common grid and voltage-transformation stages.
E0/E2 electricity and all process-heat factors come from exact local markets.
"""

ENERGY_SCENARIO_VERSION = 'paired-energy-2026-10-v2'

SCENARIOS = {
    'E0': {
        'label': 'E0 · German medium-voltage grid + natural-gas process heat',
        'name': 'market for electricity, medium voltage',
        'location': 'DE',
        'heat_name': 'market for heat, district or industrial, natural gas',
        'heat_location': 'Europe without Switzerland',
    },
    'E1': {
        'label': 'E1 · Delivered lignite electricity + non-natural-gas process heat',
        'name': 'Derived DE medium-voltage supply from lignite',
        'location': 'DE',
        'factor': 1.2934014829335918,
        'generation_code': '899bb71820e2d0014c0f65ded1e46b41',
        'generation_name': 'electricity production, lignite',
        'heat_name': 'market for heat, district or industrial, other than natural gas',
        'heat_location': 'Europe without Switzerland',
    },
    'E2': {
        'label': 'E2 · Renewable-products medium-voltage electricity + future heat',
        'name': 'market for electricity, medium voltage, renewable energy products',
        'location': 'CH',
        'heat_name': 'market for heat, future',
        'heat_location': 'GLO',
    },
}

# Provider identities recorded in the same S3 inventory. These checks prevent
# reusing the E1 paper factor against another ecoinvent import with other codes.
DELIVERY_CODES = {
    '2bf03d6f26170fb34a9a28a44375518f': 'market for electricity, medium voltage',
    '733f68d4aa4798eb1a4e5ae2c71e0de8': 'market for electricity, high voltage',
    'cc0b114d5860e380a3df0fcb5892e4d4': 'electricity voltage transformation from high to medium voltage',
}
