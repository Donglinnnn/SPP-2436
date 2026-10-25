from typing import Any, Tuple
from math import isfinite
import json

from src.contracts import SUPPORTED_PRODUCT_TYPES
from src.recipes.model_contract import require_current_processes, require_current_settings
from src.recipes.co2_sources import SOURCES as CO2_SOURCES


def validate_project_payload(payload: dict[str, Any]) -> tuple[bool, str]:
    if not isinstance(payload, dict):
        return False, "A project object is required."
    material = payload.get("material") or {}
    processes = payload.get("processes") or []

    if not isinstance(material, dict) or not isinstance(processes, list):
        return False, "Material must be an object and processes must be a list."
    settings = payload.get('lca_settings', {})
    if not isinstance(settings, dict):
        return False, 'LCA settings must be an object.'
    try:
        require_current_settings(settings, label='Project')
        require_current_processes(processes, label='Project')
    except ValueError as exc:
        return False, str(exc)
    if settings.get('electricity_scenario', 'E0') not in ('E0', 'E1', 'E2'):
        return False, 'Choose E0, E1 or E2 as one paired electricity and heat scenario.'
    if settings.get('co2_source', 'C0') not in CO2_SOURCES or 'co2_supply_factor' in settings:
        return False, 'Choose C0, C1 or C2 as the CO2 supply source; a supplied factor is unsupported.'
    if any(key in settings for key in ('electricity_code', 'heat_code', 'electricity_source', 'heat_source', 'heat_market')):
        return False, 'Choose one paired energy scenario rather than separate electricity or heat providers.'
    for process in processes:
        if not isinstance(process, dict):
            return False, 'Each process must be an object.'
    try:
        json.dumps(payload.get('lca_settings', {}), allow_nan=False)
    except (TypeError, ValueError, OverflowError):
        return False, 'LCA settings must contain finite JSON values.'
    try:
        functional_unit = payload.get("functional_unit_kg", 1)
        if isinstance(functional_unit, bool) or not isfinite(float(functional_unit)) or float(functional_unit) <= 0:
            return False, "Final dry-product mass must be a finite number greater than zero."
    except (TypeError, ValueError, OverflowError):
        return False, "Final dry-product mass must be a finite number greater than zero."

    if payload.get("product_type") not in SUPPORTED_PRODUCT_TYPES:
        return False, "MVP currently supports SCM projects only."
    if not material.get("material_name"):
        return False, "Material name is required."
    if not processes:
        return False, "Select at least one active process."
    return True, ""
