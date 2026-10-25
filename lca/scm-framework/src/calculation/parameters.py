"""Shared API parameter definitions, unit conversion, validation and provenance."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from math import isfinite
from typing import Any

from .schemas import ProcessInput


@dataclass(frozen=True)
class ParameterSpec:
    unit: str = ""
    kind: str = "number"
    required: bool = False
    default: Any = None
    minimum: float | None = 0.0
    maximum: float | None = None
    exclusive_minimum: bool = False
    choices: tuple[str, ...] = ()
    conversions: dict[str, float] = field(default_factory=dict)
    description: str = ""


def number(unit="", **kwargs):
    return ParameterSpec(unit=unit, **kwargs)


def text_spec(**kwargs):
    return ParameterSpec(kind="string", minimum=None, **kwargs)


def json_spec(**kwargs):
    return ParameterSpec(kind="json", unit="table/json/text", minimum=None, **kwargs)


SIZE = {"µm": 1.0, "μm": 1.0, "mm": 1000.0}
MASS_RATIO = {"kg/kg": 1.0, "kg/kg solid": 1.0, "kg/t": 0.001}


def validate_json_numbers(value):
    if isinstance(value, float) and not isfinite(value):
        raise ValueError("JSON numbers must be finite")
    if isinstance(value, dict):
        for item in value.values():
            validate_json_numbers(item)
    if isinstance(value, list):
        for item in value:
            validate_json_numbers(item)


class Parameters:
    def __init__(self, process: ProcessInput, specs: dict[str, ParameterSpec]):
        self.values = {}
        self.provenance = {}
        self.warnings = []
        records = {}
        for record in process.parameters:
            code = record.parameter_code.strip()
            if code in records:
                raise ValueError(f"Duplicate parameter: {code}")
            records[code] = record
            if code not in specs and record.value.strip():
                raise ValueError(f"Unsupported parameter: {code}; see /api/v1/calculation-schema")
        for code, spec in specs.items():
            record = records.get(code)
            raw = record.value.strip() if record else ""
            if raw == "":
                if spec.required:
                    raise ValueError(f"Required parameter is missing: {code}")
                value = spec.default
                origin = "model_default" if value is not None else "not_supplied"
            else:
                value = self._parse(code, raw, record.unit, spec)
                origin = "provided"
            self.values[code] = value
            self.provenance[code] = {
                "value": value, "unit": spec.unit, "origin": origin,
                "provenance": record.provenance if record else None,
                "source_note": record.source_note if record else None,
            }
        defaults = [k for k, v in self.provenance.items() if v["origin"] == "model_default"]
        if defaults:
            self.warnings.append("Model defaults used: " + ", ".join(defaults))

    @staticmethod
    def _parse(code, raw, unit, spec):
        if spec.kind == "json":
            try:
                value = json.loads(raw)
                validate_json_numbers(value)
            except (ValueError, TypeError) as exc:
                raise ValueError(f"{code}: valid finite JSON required") from exc
            return value
        if spec.kind == "boolean":
            if raw.lower() not in {"true", "false", "1", "0"}:
                raise ValueError(f"{code}: expected true or false")
            return raw.lower() in {"true", "1"}
        if spec.kind == "string":
            if spec.choices and raw not in spec.choices:
                raise ValueError(f"{code}: expected one of {spec.choices}")
            return raw
        try:
            value = float(raw)
        except ValueError as exc:
            raise ValueError(f"{code}: expected a number") from exc
        if not isfinite(value):
            raise ValueError(f"{code}: expected a finite number")
        unit = unit.strip()
        if unit and unit != spec.unit:
            if unit not in spec.conversions:
                raise ValueError(f"{code}: unsupported unit {unit!r}; expected {spec.unit!r}")
            value *= spec.conversions[unit]
        if spec.minimum is not None and (value < spec.minimum or (spec.exclusive_minimum and value == spec.minimum)):
            raise ValueError(f"{code}: must be {'>' if spec.exclusive_minimum else '>='} {spec.minimum}")
        if spec.maximum is not None and value > spec.maximum:
            raise ValueError(f"{code}: must be <= {spec.maximum}")
        return value


def calculation_schema():
    from .input_catalogue import input_libraries
    from .process_settings.carbonation import (GENERAL_CONDITION_SPECS, GENERAL_VARIANT,
        INPUT_DEFAULTS_VERSION, carbonation_defaults_library)
    from .process_settings.crushing import CRUSHING_SPECS
    from .process_settings.grinding import GRINDING_SPECS
    from .supporting_data.grinding_materials import MATERIAL_WIFI_LIBRARY
    from .process_settings.separation import SCREENING_SPECS, SIEVING_SPECS, SORTING_SPECS
    from .process_settings.thermal_activation import THERMAL_SPECS
    return {
        "schema_version": "1.6",
        "input_defaults_version": INPUT_DEFAULTS_VERSION,
        "processes": {
            name: {"status": "implemented", "parameters": {code: asdict(spec) for code, spec in specs.items()}}
            for name, specs in {"Crushing": CRUSHING_SPECS, "Grinding": GRINDING_SPECS,
                                "Sieving": SIEVING_SPECS, "Screening": SCREENING_SPECS, "Sorting": SORTING_SPECS,
                                "Thermal activation": THERMAL_SPECS, "Carbonation": GENERAL_CONDITION_SPECS}.items()
        },
        "input_libraries": {**input_libraries(), "carbonation_defaults": carbonation_defaults_library()},
        "ui_default_carbonation_variant": GENERAL_VARIANT,
        "grinding_material_proxies": MATERIAL_WIFI_LIBRARY,
        "basis": "Per kg dry process product; summary per requested kg final product",
        "thermal_tga_basis": ["total_intervals"],
        "carbonation_variants": {
            GENERAL_VARIANT: {
                "status": "general",
                "parameters": {code: asdict(spec) for code, spec in GENERAL_CONDITION_SPECS.items()},
            },
        },
    }
