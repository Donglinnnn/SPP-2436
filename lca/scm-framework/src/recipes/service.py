"""Append-only material and recipe snapshots; existing projects are never mutated."""
import hashlib
import json
from uuid import uuid4

from src.db import get_connection
from src.calculation.process_settings.carbonation import INPUT_DEFAULTS_VERSION
from src.repositories.project_repository import get_project
from .calculation import calculate_recipe, characterize_scm, number, scm_foreground
from .electricity_scenarios import ENERGY_SCENARIO_VERSION
from .model_contract import IncompatibleModelError, require_current_settings


def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)


def name_from(payload):
    name = payload.get('name', '')
    if not isinstance(name, str) or not name.strip() or len(name) > 200:
        raise ValueError('A name of 1–200 characters is required')
    return name.strip()


def material(row, detail=True):
    if row is None:
        return None
    item = dict(row)
    snapshot = json.loads(item.pop('snapshot_json'))
    settings = require_current_settings(
        (snapshot.get('pathway') or {}).get('lca_settings'), label=f'Saved SCM material {item["id"]}')
    transport = snapshot.get('transport', [])
    if ((snapshot.get('electricity_source') or {}).get('unit') != 'kilowatt hour'
            or (snapshot.get('heat_source') or {}).get('unit') != 'megajoule'
            or not isinstance(transport, list)
            or any(not isinstance(leg, dict) or leg.get('key') != 'waste_to_process'
                   for leg in transport)):
        raise IncompatibleModelError(f'Incompatible saved scm material {item["id"]}: current paired-energy LCIA resolution is required.')
    item['gwp_kg_co2e_kg'] = snapshot['gwp_kg_co2e_kg']
    item['method'] = snapshot['method']
    item['background_fingerprint'] = snapshot.get('background_fingerprint')
    item['boundary'] = snapshot['boundary']
    item['source_project'] = snapshot.get('source_project')
    item['transport'] = snapshot.get('transport', [])
    item['electricity_source'] = snapshot.get('electricity_source')
    item['heat_source'] = snapshot.get('heat_source')
    item['recipe_transport'] = snapshot.get('pathway',{}).get('lca_settings',{}).get('recipe_transport')
    item['energy_scenario_version'] = settings['energy_scenario_version']
    item['input_defaults_version'] = settings['input_defaults_version']
    if detail:
        item['snapshot'] = snapshot
    return item


def get_material(item_id):
    if not isinstance(item_id, str):
        return None
    with get_connection() as conn:
        return material(conn.execute('SELECT * FROM scm_items WHERE id=?', (item_id,)).fetchone())


def list_materials():
    with get_connection() as conn:
        items = []
        for row in conn.execute('SELECT * FROM scm_items ORDER BY created_at DESC,rowid DESC'):
            try:
                items.append(material(row, False))
            except IncompatibleModelError:
                continue
        return items


def create_material(payload, *, source_project=None):
    if 'co2_supply_factor' in payload:
        raise ValueError('External CO2 supply must use C0, C1 or C2; a supplied factor is unsupported.')
    name = name_from(payload)
    density = number(payload.get('density_kg_m3'), 'SCM particle density', positive=True)
    # Ignore any client-provided factor/results. Recompute the normalized route.
    snapshot = characterize_scm(payload.get('pathway'))
    if source_project is not None:
        snapshot['source_project'] = source_project
    raw = encoded(snapshot)
    digest = hashlib.sha256(raw.encode()).hexdigest()
    item_id = str(uuid4())
    with get_connection() as conn:
        conn.execute('INSERT INTO scm_items (id,name,density_kg_m3,snapshot_json,snapshot_hash) VALUES (?,?,?,?,?)',
                     (item_id, name, density, raw, digest))
    return get_material(item_id)


def project_input(conn, project_id):
    pathway, material_input, processes = get_project(conn, project_id)
    if pathway is None or pathway['product_type'] != 'SCM':
        raise ValueError('Saved SCM project not found')
    return dict(**pathway, project_id=project_id, material=material_input,
                processes=[p for p in processes if p.get('is_active', True)])


def scm_history():
    """Current material snapshots and saved input routes, with readiness checks."""
    projects = []
    with get_connection() as conn:
        ids = [row['id'] for row in conn.execute("SELECT id FROM pathways WHERE product_type='SCM' ORDER BY id DESC")]
        for project_id in ids:
            try:
                pathway = project_input(conn, project_id)
            except IncompatibleModelError:
                continue
            issues = []
            try:
                scm_foreground(pathway)
            except (ValueError, OverflowError) as exc:
                issues.append(str(exc))
            projects.append(dict(id=project_id, name=pathway['pathway_name'],
                material_name=(pathway['material'] or {}).get('material_name', ''),
                created_at=pathway['created_at'], process_names=[p['process_name'] for p in pathway['processes']],
                lca_settings=pathway.get('lca_settings', {}),
                energy_scenario_version=pathway['energy_scenario_version'],
                input_defaults_version=pathway['input_defaults_version'],
                ready_to_package=not issues, issues=issues))
    return dict(materials=list_materials(), projects=projects)


def create_material_from_project(project_id, payload):
    if 'co2_supply_factor' in payload:
        raise ValueError('External CO2 supply must use C0, C1 or C2; a supplied factor is unsupported.')
    with get_connection() as conn:
        pathway = project_input(conn, project_id)
    # The server reads the saved inputs; client pathway/factor fields are ignored.
    return create_material(dict(name=payload.get('name') or pathway['pathway_name'],
        density_kg_m3=payload.get('density_kg_m3'),
        pathway=pathway), source_project=dict(id=project_id, name=pathway['pathway_name'], created_at=pathway['created_at']))


def calculate(payload):
    result = calculate_recipe(payload, get_material)
    result['energy_scenario_version'] = ENERGY_SCENARIO_VERSION
    result['input_defaults_version'] = INPUT_DEFAULTS_VERSION
    return result


def create_recipe(payload):
    name = name_from(payload)
    result = calculate(payload)
    recipe_id = str(uuid4())
    with get_connection() as conn:
        conn.execute('INSERT INTO recipe_records (id,name,payload_json,result_json) VALUES (?,?,?,?)',
                     (recipe_id, name, encoded(payload), encoded(result)))
    return get_recipe(recipe_id)


def get_recipe(recipe_id):
    with get_connection() as conn:
        row = conn.execute('SELECT * FROM recipe_records WHERE id=?', (recipe_id,)).fetchone()
    if row is None:
        return None
    result = dict(row)
    result['payload'] = json.loads(result.pop('payload_json'))
    result['result'] = json.loads(result.pop('result_json'))
    versions = require_current_settings(result['result'], label=f'Saved recipe {recipe_id}')
    result['energy_scenario_version'] = versions['energy_scenario_version']
    result['input_defaults_version'] = versions['input_defaults_version']
    return result


def list_recipes():
    with get_connection() as conn:
        rows = conn.execute('SELECT id,name,created_at,result_json FROM recipe_records ORDER BY created_at DESC,rowid DESC')
        items = []
        for row in rows:
            item = dict(row)
            result = json.loads(item.pop('result_json'))
            try:
                versions = require_current_settings(result, label=f'Saved recipe {item["id"]}')
            except IncompatibleModelError:
                continue
            item['energy_scenario_version'] = versions['energy_scenario_version']
            item['input_defaults_version'] = versions['input_defaults_version']
            items.append(item)
        return items
