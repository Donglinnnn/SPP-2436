"""Add an auditable A–B–C sidecar to an already evaluated calculation.

This module reads the quantities produced by the adapters and chain engine. It
does not generate exchanges, apply yields again, or select background providers.
"""
from copy import deepcopy
import csv
import hashlib
import io
import json
from math import isfinite


SCHEMA_VERSION = "1.0"


def _json_safe_metadata(value):
    """Preserve non-finite free-text metadata explicitly without breaking a run.

    Calculation inputs are validated by the adapters; optional descriptive
    route/material fields can still contain arbitrary JSON values.
    """
    if isinstance(value, float) and not isfinite(value):
        return {"non_finite_number": repr(value)}
    if isinstance(value, dict):
        return {key: _json_safe_metadata(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe_metadata(item) for item in value]
    return value


def build_run_record(request, items, summary, *, functional_unit_kg, errors=()):
    """Record input provenance, native exchanges, normalization and final flows."""
    operations, parameters, native_rows, final_rows = [], [], [], []
    steps = {step["process_order"]: step for step in summary.get("steps", [])}
    items_by_order = {item.process_order: item for item in items}
    for process in sorted(request.processes, key=lambda value: value.process_order):
        operation_id = f"op-{process.process_order}"
        item = items_by_order.get(process.process_order)
        meta = item.metadata if item else {}
        effective = meta.get("parameters", {})
        # Preserve every supplied row, including unrecognized/duplicate fields;
        # effective values are the actual parsed values used by the adapter.
        supplied = {}
        for parameter in process.parameters:
            supplied.setdefault(parameter.parameter_code, []).append({
                "value": parameter.value, "unit": parameter.unit,
                "label": parameter.parameter_label, "provenance": parameter.provenance,
                "source_note": parameter.source_note,
            })
        for code in dict.fromkeys([*supplied, *effective]):
            actual = effective.get(code)
            parameters.append({
                "parameter_id": f"{operation_id}:{code}", "operation_id": operation_id,
                "process_name": process.process_name, "parameter_code": code,
                "supplied": supplied.get(code, []),
                "effective": deepcopy(actual),
                "status": "recorded_effective_value" if actual is not None else "not_resolved",
            })
        recording = meta.get("recording", {})
        operations.append({
            "operation_id": operation_id, "process_name": process.process_name,
            "process_order": process.process_order,
            "status": meta.get("status", "not_calculated"),
            "source_file": meta.get("source_file"),
            "process_basis": meta.get("basis"),
            "native_basis": recording.get("native_basis"),
            "normalization_note": recording.get("normalization_note"),
            "details": deepcopy(meta.get("details", {})),
        })
        for key, quantity in meta.get("inventory", {}).items():
            annotation = recording.get("exchange_metadata", {}).get(key, {})
            native_inventory = recording.get("native_inventory", {})
            has_native = "native_quantity" in annotation or key in native_inventory
            role = annotation.get("role", "diagnostic" if quantity == 0 else "exchange")
            row = {
                "exchange_id": f"{operation_id}:{key}", "operation_id": operation_id,
                "process_name": process.process_name, "process_order": process.process_order,
                "flow_key": key, "flow_name": key,
                "unit": annotation.get("unit"),
                "exchange_type": annotation.get("exchange_type", "unclassified"),
                "generation_layer": annotation.get("generation_layer"),
                "source_reference": annotation.get("source_reference"),
                "role": role, "alias_of": annotation.get("alias_of"),
                "parameter_refs": [f"{operation_id}:{code}" for code in annotation.get("parameter_codes", [])],
                "native_quantity": annotation.get("native_quantity", native_inventory.get(key, quantity)),
                "native_basis": annotation.get("native_basis", recording.get("native_basis")) if has_native else meta.get("basis"),
                "normalization_factor_to_process_product": annotation.get(
                    "normalization_factor_to_process_product", recording.get("normalization_factor_to_process_product", 1.0)) if has_native else 1.0,
                "process_quantity": quantity,
                "process_basis": meta.get("basis"),
                "native_record_status": "recorded" if has_native else "product_basis_only",
                "note": annotation.get("note"),
            }
            native_rows.append(row)
            step = steps.get(process.process_order)
            if step is None:
                continue
            # Upstream feed is a reference link, not a second burden exchange.
            upstream = key == "upstream_input_kg"
            final_rows.append({
                **deepcopy(row),
                "quantity": step["required_input_kg"] if upstream else step["contributions"].get(key),
                "allocated_quantity": None if upstream else step["allocated_contributions"].get(key),
                "quantity_basis": "requested_final_dry_product",
                "route_scaling_factor": step["required_output_kg"],
                "burden_allocation_factor": step["burden_allocation_factor"],
                "included_in_physical_inventory": not upstream and role == "exchange" and not row["alias_of"],
                "provider_status": "reference_flow" if upstream else "not_resolved",
                "provider": None,
            })
    complete = summary.get("status") == "complete" and not errors
    record = {
        "schema_version": SCHEMA_VERSION,
        "route": {
            "project_id": request.project_id, "pathway_name": request.pathway_name,
            "reference_product": request.reference_product, "system_boundary": request.system_boundary,
            "functional_unit_kg": functional_unit_kg,
            "material": deepcopy(vars(request.material)) if request.material else None,
        },
        "inputs": parameters,
        "A": {"operations": operations, "exchanges": native_rows},
        "B": {
            "status": summary.get("status", "incomplete"), "basis": summary.get("basis"),
            "steps": deepcopy(summary.get("steps", [])),
            "initial_feed_required_kg": summary.get("initial_feed_required_kg"),
            "physical_totals": deepcopy(summary.get("totals", {})),
            "allocated_totals": deepcopy(summary.get("allocated_totals", {})),
            "allocation_note": summary.get("allocation_note"),
            "boundary": summary.get("boundary"),
            "note": "Engine totals are retained unchanged, including diagnostic and alias keys. They are not an independently characterized inventory.",
        },
        "C": {
            "status": "unlinked_foreground" if complete else "incomplete",
            "basis": "requested_final_dry_product", "exchanges": final_rows,
            "provider_links": [], "lcia_status": "not_calculated",
            "note": "Reference links, aliases and diagnostics are retained for traceability; do not sum all rows. Actual LCIA resolution is recorded separately after successful characterization.",
        },
        "errors": list(errors),
    }
    record = _json_safe_metadata(record)
    serialized = json.dumps(record, sort_keys=True, ensure_ascii=False, allow_nan=False)
    record["run_id"] = hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:20]
    return record


def export_record_json(record):
    """Export the complete record; no background database is required."""
    return json.dumps(record, indent=2, ensure_ascii=False, allow_nan=False) + "\n"


def export_record_csv(record, table="C"):
    """Export one trace table; JSON cells retain nested provenance/identities."""
    tables = {
        "inputs": record.get("inputs", []),
        "A": record.get("A", {}).get("exchanges", []),
        "B": record.get("B", {}).get("steps", []),
        "C": record.get("C", {}).get("exchanges", []),
        "providers": record.get("C", {}).get("lcia_resolution", record.get("C", {})).get("provider_links", []),
    }
    if table not in tables:
        raise ValueError("table must be inputs, A, B, C or providers")
    rows = tables[table]
    fields = list(dict.fromkeys(["run_id", "schema_version", *[key for row in rows for key in row]]))
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fields)
    writer.writeheader()
    for row in rows:
        values = {"run_id": record.get("run_id"), "schema_version": record.get("schema_version"), **row}
        for key, value in values.items():
            if isinstance(value, (dict, list)):
                values[key] = json.dumps(value, ensure_ascii=False, allow_nan=False)
            elif isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
                values[key] = "'" + value  # Keep text inert when opened in Excel.
        writer.writerow(values)
    return stream.getvalue()
