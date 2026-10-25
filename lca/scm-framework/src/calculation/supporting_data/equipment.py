"""Adopted Piccinno-style reactor reference configuration.

These are equipment reference assumptions, not universal properties. The 1.0
fill fraction describes this reference configuration; the calculation's wet-route
default is selected in process_settings/carbonation_defaults.py.
"""

# Piccinno-style 10,000 L stirred reactor scenario used when route-specific
# equipment data are not supplied.
PICCINNO_MIXTURE_VOLUME_M3 = 10.0
PICCINNO_REACTOR_VOLUME_M3 = PICCINNO_MIXTURE_VOLUME_M3
PICCINNO_REACTOR_FILL_FRACTION = 1.0
PICCINNO_MIXING_POWER_NUMBER = 0.79
PICCINNO_IMPELLER_SPEED_PER_S = 0.658
PICCINNO_IMPELLER_DIAMETER_M = 0.803
PICCINNO_STIRRING_EFFICIENCY = 0.90
PICCINNO_TANK_DIAMETER_M = 2.41
PICCINNO_GAS_EFFICIENCY = 0.30
