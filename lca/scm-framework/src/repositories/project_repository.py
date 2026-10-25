import json
import sqlite3
from typing import Any

from src.db import row_to_dict
from src.contracts import parameter_value_text
from src.recipes.model_contract import (
    IncompatibleModelError, require_current_processes, require_current_settings,
)


def list_projects(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
            p.id,
            p.product_type,
            p.pathway_name,
            p.reference_product,
            p.system_boundary,
            p.location,
            p.flow_chart_json,
            p.lca_settings_json,
            p.created_at,
            m.material_type,
            m.material_name,
            COUNT(pi.id) AS process_count
        FROM pathways p
        LEFT JOIN materials m ON m.pathway_id = p.id
        LEFT JOIN process_instances pi ON pi.pathway_id = p.id
        GROUP BY p.id
        ORDER BY p.id DESC
        """
    ).fetchall()

    projects: list[dict[str, Any]] = []
    for row in rows:
        item = row_to_dict(row)
        flow_chart_raw = item.pop("flow_chart_json")
        item["flow_chart"] = json.loads(flow_chart_raw) if flow_chart_raw else []
        settings = json.loads(item.pop("lca_settings_json") or "{}")
        try:
            require_current_settings(settings, label=f'Saved project #{item["id"]}')
            # Reuse the detail reader's process-model check so an incompatible
            # imported route is never advertised as an openable current project.
            get_project(conn, item['id'])
        except IncompatibleModelError:
            continue
        item["energy_scenario_version"] = settings.get("energy_scenario_version")
        item["input_defaults_version"] = settings.get("input_defaults_version")
        projects.append(item)
        if len(projects) == 30:
            break
    return projects


def get_project(conn: sqlite3.Connection, project_id: int) -> tuple[dict[str, Any] | None, dict[str, Any] | None, list[dict[str, Any]]]:
    pathway = conn.execute("SELECT * FROM pathways WHERE id = ?", (project_id,)).fetchone()
    if pathway is None:
        return None, None, []
    settings = json.loads(pathway['lca_settings_json'] or '{}')
    require_current_settings(settings, label=f'Saved project #{project_id}')

    material = conn.execute(
        "SELECT * FROM materials WHERE pathway_id = ?",
        (project_id,),
    ).fetchone()

    processes = conn.execute(
        """
        SELECT *
        FROM process_instances
        WHERE pathway_id = ?
        ORDER BY process_order ASC, id ASC
        """,
        (project_id,),
    ).fetchall()

    process_payload = []
    for process in processes:
        parameters = conn.execute(
            """
            SELECT parameter_code, parameter_label, value, unit, provenance, source_note
            FROM parameter_values
            WHERE process_instance_id = ?
            ORDER BY id ASC
            """,
            (process["id"],),
        ).fetchall()
        process_item = row_to_dict(process)
        process_item["parameters"] = [row_to_dict(row) for row in parameters]
        process_payload.append(process_item)

    pathway_payload = row_to_dict(pathway)
    flow_chart_raw = pathway_payload.pop("flow_chart_json")
    pathway_payload["flow_chart"] = json.loads(flow_chart_raw) if flow_chart_raw else []
    require_current_processes(process_payload, label=f'Saved project #{project_id}')
    pathway_payload.pop('lca_settings_json', None)
    pathway_payload['lca_settings'] = settings
    pathway_payload['energy_scenario_version'] = settings['energy_scenario_version']
    pathway_payload['input_defaults_version'] = settings['input_defaults_version']
    return pathway_payload, (row_to_dict(material) if material else None), process_payload


def create_project_record(conn: sqlite3.Connection, payload: dict[str, Any], *, default_material_type: str, default_reference_product: str, default_system_boundary: str) -> int:
    require_current_settings(payload.get('lca_settings'), label='Project')
    require_current_processes(payload.get('processes'), label='Project')
    material = payload["material"]
    processes = payload["processes"]
    location = material.get("location") or payload.get("location") or ""
    flow_chart = payload.get("flow_chart") or []
    pathway_name = payload.get("pathway_name") or f"{material['material_name']} SCM"

    cursor = conn.execute(
        """
        INSERT INTO pathways (
            product_type,
            pathway_name,
            reference_product,
            system_boundary,
                location,
                flow_chart_json,
                functional_unit_kg,
                lca_settings_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payload["product_type"],
            pathway_name,
            payload.get("reference_product") or default_reference_product,
            payload.get("system_boundary") or default_system_boundary,
            location,
            json.dumps(flow_chart),
            float(payload.get("functional_unit_kg", 1)),
            json.dumps({key: value for key, value in payload.get('lca_settings', {}).items()
                        if key != 'model_version'}, allow_nan=False),
        ),
    )
    pathway_id = cursor.lastrowid

    conn.execute(
        """
        INSERT INTO materials (
            pathway_id,
            material_type,
            material_name,
            feedstock_burden_rule,
            note
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            pathway_id,
            material.get("material_type") or default_material_type,
            material["material_name"],
            material.get("feedstock_burden_rule") or "",
            material.get("note") or "",
        ),
    )

    for index, process in enumerate(processes, start=1):
        cursor = conn.execute(
            """
            INSERT INTO process_instances (
                pathway_id,
                process_name,
                process_order,
                is_active
            )
            VALUES (?, ?, ?, 1)
            """,
            (pathway_id, process["process_name"], process.get("process_order") or index),
        )
        process_id = cursor.lastrowid

        for parameter in process.get("parameters") or []:
            conn.execute(
                """
                INSERT INTO parameter_values (
                    process_instance_id,
                    parameter_code,
                    parameter_label,
                    value,
                    unit,
                    provenance,
                    source_note
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    process_id,
                    parameter.get("parameter_code") or "",
                    parameter.get("parameter_label") or "",
                    parameter_value_text(parameter.get("value")),
                    parameter.get("unit") or "",
                    parameter.get("provenance") or "",
                    parameter.get("source_note") or "",
                ),
            )

    return pathway_id
