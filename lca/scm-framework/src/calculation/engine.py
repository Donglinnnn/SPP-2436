from __future__ import annotations

from collections.abc import Callable
from math import isfinite

from .chain import summarize_chain
from .recording import build_run_record

from .modules.general_conditions_carbonation import calculate_general_conditions as calculate_carbonation
from .modules.crushing import calculate_crushing
from .modules.grinding import calculate_grinding
from .modules.sieving import calculate_sieving
from .modules.screening import calculate_screening
from .modules.sorting import calculate_sorting
from .modules.thermal_activation import calculate_thermal_activation
from .normalizer import normalize_process
from .schemas import CalculationRequest, CalculationResponse, CalculationItem


CalculationEngine = Callable[[object], CalculationItem]
UNIMPLEMENTED_STANDALONE_PROCESSES = frozenset({"Washing", "Drying", "Blending"})


def validate_request(payload):
    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object")
    if payload.get("product_type", "SCM") != "SCM":
        raise ValueError("Only SCM is supported")
    project_id = payload.get("project_id")
    if project_id is not None and (type(project_id) is not int or project_id <= 0):
        raise ValueError("project_id must be a positive integer when supplied")
    if payload.get("material") is not None and not isinstance(payload["material"], dict):
        raise ValueError("material must be an object")
    processes = payload.get("processes")
    if not isinstance(processes, list) or not processes:
        raise ValueError("At least one process is required")
    orders = set()
    for idx, process in enumerate(processes):
        if not isinstance(process, dict) or not isinstance(process.get("process_name"), str):
            raise ValueError("Each process needs a process_name string")
        order = process.get("process_order", idx + 1)
        if isinstance(order, bool) or not isinstance(order, (int, str)) or not str(order).isdigit() or int(order) <= 0:
            raise ValueError("process_order must be a positive integer")
        if int(order) in orders:
            raise ValueError("process_order values must be unique")
        orders.add(int(order))
        parameters = process.get("parameters", [])
        if not isinstance(parameters, list):
            raise ValueError("parameters must be a list")
        for param in parameters:
            if not isinstance(param, dict) or not isinstance(param.get("parameter_code"), str):
                raise ValueError("Each parameter needs a parameter_code string")
            for key in ("unit", "parameter_label", "provenance", "source_note"):
                if param.get(key) is not None and not isinstance(param[key], str):
                    raise ValueError(f"{key} must be a string")
    fu = payload.get("functional_unit_kg", 1.0)
    if isinstance(fu, bool) or not isinstance(fu, (int, float)) or not isfinite(fu) or fu <= 0:
        raise ValueError("functional_unit_kg must be a finite positive number")
    return fu


def get_calculation_strategy_map() -> dict[str, CalculationEngine]:
    return {
        "Crushing": calculate_crushing,
        "Grinding": calculate_grinding,
        "Sieving": calculate_sieving,
        "Screening": calculate_screening,
        "Sorting": calculate_sorting,
        "Thermal activation": calculate_thermal_activation,
        "Carbonation": calculate_carbonation,
    }


def run_calculation(payload: dict[str, object]) -> CalculationResponse:
    try:
        final_product_kg = validate_request(payload)
        request = CalculationRequest.from_payload(payload)
    except (ValueError, TypeError, OverflowError) as exc:
        return CalculationResponse(
            project_id=None,
            ok=False, errors=[str(exc)], summary={"status": "incomplete"})
    warnings: list[str] = []
    errors: list[str] = []
    items: list[CalculationItem] = []

    strategy_map = get_calculation_strategy_map()

    for process in sorted(request.processes, key=lambda p: p.process_order):
        normalized = normalize_process(process)
        calc_fn = strategy_map.get(normalized.process_name)

        if calc_fn is None:
            if normalized.process_name in UNIMPLEMENTED_STANDALONE_PROCESSES:
                errors.append(
                    f"{normalized.process_name}: this standalone process was never implemented; "
                    "the saved inputs remain available, but remove or replace this step to calculate the route"
                )
            else:
                errors.append(f"No calculation strategy for process: {normalized.process_name}")
            continue

        try:
            item = calc_fn(normalized)
            items.append(item)
            if item.metadata.get("status") != "calculated":
                errors.append(f"{normalized.process_name}: formula migration not implemented")
            warnings.extend(f"{normalized.process_name}: {warning}" for warning in item.metadata.get("warnings", []))
        except Exception as exc:  # pragma: no cover - guardrail for future formula code
            errors.append(f"Failed process {normalized.process_name}: {exc}")

    summary = {"status": "incomplete", "lcia_status": "not_calculated"}
    if not errors:
        if len(items) > 1 and any(not item.metadata.get("chain_compatible", False) for item in items):
            errors.append("Multi-component feed needs explicit upstream mapping before calculating a chain total")
        else:
            try:
                summary = summarize_chain(items, final_product_kg)
            except ValueError as exc:
                errors.append(str(exc))
    ok = not errors
    return CalculationResponse(
        project_id=request.project_id,
        ok=ok,
        items=items,
        warnings=warnings,
        errors=errors,
        summary=summary,
        records=build_run_record(request, items, summary,
                                 functional_unit_kg=final_product_kg, errors=errors),
    )
