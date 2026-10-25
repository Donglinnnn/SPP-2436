from flask import Blueprint, jsonify, request

from src.contracts import DEFAULT_MATERIAL_TYPE, DEFAULT_REFERENCE_PRODUCT, DEFAULT_SYSTEM_BOUNDARY
from src.db import get_connection
from src.repositories.project_repository import create_project_record, get_project, list_projects
from src.services.project_service import validate_project_payload


def register_project_routes(blueprint: Blueprint) -> None:
    @blueprint.get("/projects")
    def list_projects_endpoint():
        try:
            with get_connection() as conn:
                projects = list_projects(conn)
        except ValueError as exc:
            return jsonify(ok=False, error=str(exc)), 422
        return jsonify(projects)

    @blueprint.get("/projects/<int:project_id>")
    def get_project_endpoint(project_id: int):
        try:
            with get_connection() as conn:
                pathway, material, processes = get_project(conn, project_id)
        except ValueError as exc:
            return jsonify(ok=False, error=str(exc)), 422
        if pathway is None:
            return jsonify({"ok": False, "error": "Project not found."}), 404

        return jsonify(
            {
                "pathway": pathway,
                "material": material,
                "processes": processes,
            }
        )

    @blueprint.post("/projects")
    def create_project_endpoint():
        payload = request.get_json(force=True, silent=True) or {}
        is_valid, message = validate_project_payload(payload)
        if not is_valid:
            return jsonify({"ok": False, "error": message}), 400

        with get_connection() as conn:
            pathway_id = create_project_record(
                conn,
                payload,
                default_material_type=DEFAULT_MATERIAL_TYPE,
                default_reference_product=DEFAULT_REFERENCE_PRODUCT,
                default_system_boundary=DEFAULT_SYSTEM_BOUNDARY,
            )

        response_data = {"id": pathway_id, "message": "Project saved."}
        return (
            jsonify({"ok": True, "data": response_data, **response_data}),
            201,
        )
