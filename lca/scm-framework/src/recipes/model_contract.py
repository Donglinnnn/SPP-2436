"""Version contract for saved inputs and results used by the current model."""

import math

from src.calculation.process_settings.carbonation import (
    GENERAL_VARIANT as CARBONATION_MODEL,
    INPUT_DEFAULTS_VERSION,
)
from .co2_sources import SOURCES as CO2_SOURCES
from .electricity_scenarios import ENERGY_SCENARIO_VERSION, SCENARIOS


class IncompatibleModelError(ValueError):
    """A saved record cannot be interpreted under the current model."""


def require_current_settings(settings, *, label='Route'):
    if not isinstance(settings, dict):
        raise IncompatibleModelError(f'Incompatible {label.lower()}: current LCA settings are required.')
    if (settings.get('energy_scenario_version') != ENERGY_SCENARIO_VERSION
            or settings.get('input_defaults_version') != INPUT_DEFAULTS_VERSION):
        raise IncompatibleModelError(
            f'Incompatible {label.lower()}: the current paired-energy '
            'and input-default definitions are required. Recreate the record with current inputs.')
    if 'co2_supply_factor' in settings:
        raise IncompatibleModelError(f'Incompatible {label.lower()}: a supplied CO2 factor is unsupported; choose C0, C1 or C2.')
    if settings.get('co2_source', 'C0') not in CO2_SOURCES:
        raise IncompatibleModelError(f'Incompatible {label.lower()}: choose C0, C1 or C2 as the CO2 source.')
    if (settings.get('electricity_scenario', 'E0') not in SCENARIOS
            or any(key in settings for key in
                   ('electricity_code', 'heat_code', 'electricity_source', 'heat_source', 'heat_market'))):
        raise IncompatibleModelError(f'Incompatible {label.lower()}: one E0/E1/E2 choice must select the electricity and heat pair.')
    transport = settings.get('transport', {})
    if not isinstance(transport, dict) or set(transport) - {'waste_to_process'}:
        raise IncompatibleModelError(f'Incompatible {label.lower()}: SCM delivery belongs in the recipe, not the SCM route.')
    inbound = transport.get('waste_to_process', {})
    if not isinstance(inbound, dict):
        raise IncompatibleModelError(f'Incompatible {label.lower()}: inbound waste transport must be an object.')
    moisture = inbound.get('moisture_percent', 0)
    try:
        moisture = float(moisture) if not isinstance(moisture, bool) else math.nan
    except (TypeError, ValueError):
        moisture = math.nan
    if not math.isfinite(moisture) or moisture != 0:
        raise IncompatibleModelError(f'Incompatible {label.lower()}: inbound waste transport moisture must be zero.')
    return settings


def require_current_processes(processes, *, label='Route'):
    for process in processes or []:
        if not isinstance(process, dict) or process.get('process_name') != 'Carbonation':
            continue
        for row in process.get('parameters') or []:
            if (isinstance(row, dict) and row.get('parameter_code') == 'carbonation_model'
                    and row.get('value') != CARBONATION_MODEL):
                raise IncompatibleModelError(f'Incompatible {label.lower()}: unsupported Carbonation model.')
