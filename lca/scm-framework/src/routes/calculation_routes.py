from __future__ import annotations

from flask import Blueprint, Response, jsonify, request

from src.services.calculation_service import calculate_project
from src.calculation.parameters import calculation_schema
from src.calculation.recording import export_record_csv, export_record_json
from src.recipes.model_contract import require_current_processes, require_current_settings


def unsupported_model_error(payload):
    if not isinstance(payload, dict):
        return None
    try:
        require_current_settings(payload.get('lca_settings'), label='Route')
        require_current_processes(payload.get('processes'), label='Route')
    except ValueError as exc:
        return str(exc)
    return None


def register_calculation_routes(blueprint: Blueprint) -> None:
    @blueprint.get("/calculation-schema")
    def calculation_schema_endpoint():
        return jsonify(calculation_schema())

    @blueprint.post("/calculate")
    def calculate_endpoint():
        payload = request.get_json(silent=True)
        if error := unsupported_model_error(payload):
            return jsonify(ok=False, errors=[error]), 422
        result = calculate_project(payload)
        return jsonify(result), 200 if result["ok"] else 422

    @blueprint.post("/calculate/export")
    def export_calculation_record():
        output_format = request.args.get("format", "json")
        table = request.args.get("table", "C")
        if output_format not in ("json", "csv"):
            return jsonify(error="format must be json or csv"), 400
        payload = request.get_json(silent=True)
        if error := unsupported_model_error(payload):
            return jsonify(ok=False, errors=[error]), 422
        result = calculate_project(payload)
        if not result["ok"]:
            return jsonify(result), 422
        try:
            content = (export_record_json(result["records"]) if output_format == "json"
                       else export_record_csv(result["records"], table))
        except ValueError as exc:
            return jsonify(error=str(exc)), 400
        return Response(content, mimetype="application/json" if output_format == "json" else "text/csv",
                        headers={"Content-Disposition": f'attachment; filename="scm-abc-record.{output_format}"'})
