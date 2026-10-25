"""Saved records without the current model contract are rejected on read."""
import json
import sqlite3
import unittest
from unittest.mock import patch

from src.application import create_app
from src.repositories.project_repository import get_project, list_projects
from src.services.project_service import validate_project_payload
from src.recipes import service
from src.recipes.model_contract import require_current_settings
from src.recipes.calculation import recipe_transport
from src.recipes.electricity_scenarios import ENERGY_SCENARIO_VERSION
from src.calculation.process_settings.carbonation import INPUT_DEFAULTS_VERSION


def current_settings():
    return dict(energy_scenario_version=ENERGY_SCENARIO_VERSION,
                input_defaults_version=INPUT_DEFAULTS_VERSION, electricity_scenario='E1')


def project_database():
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    conn.executescript('''
        CREATE TABLE pathways (id INTEGER PRIMARY KEY, product_type TEXT,
            pathway_name TEXT, reference_product TEXT, system_boundary TEXT,
            location TEXT, flow_chart_json TEXT, lca_settings_json TEXT, created_at TEXT);
        CREATE TABLE materials (id INTEGER PRIMARY KEY, pathway_id INTEGER,
            material_type TEXT, material_name TEXT, feedstock_burden_rule TEXT, note TEXT);
        CREATE TABLE process_instances (id INTEGER PRIMARY KEY, pathway_id INTEGER,
            process_name TEXT, process_order INTEGER, is_active INTEGER);
        CREATE TABLE parameter_values (id INTEGER PRIMARY KEY, process_instance_id INTEGER,
            parameter_code TEXT, parameter_label TEXT, value TEXT, unit TEXT,
            provenance TEXT, source_note TEXT);
    ''')
    for project_id, settings in ((1, {'electricity_scenario': 'E1'}),
                                 (2, current_settings()),
                                 (3, current_settings()),
                                 (4, dict(current_settings(), transport={'scm_to_mix': {'enabled': False}})),
                                 (5, dict(current_settings(), transport={'waste_to_process': {'enabled': True, 'distance_km': 10, 'moisture_percent': 5}})),
                                 (6, dict(current_settings(), transport={'waste_to_process': {'enabled': True, 'distance_km': 10, 'moisture_percent': 0}}))):
        conn.execute('INSERT INTO pathways VALUES (?,?,?,?,?,?,?,?,?)',
            (project_id, 'SCM', f'Project {project_id}', 'SCM', 'A1-A3', 'DE', '[]',
             json.dumps(settings), '2026-10-15'))
    conn.execute("INSERT INTO process_instances VALUES (3,3,'Carbonation',1,1)")
    conn.execute("INSERT INTO parameter_values VALUES (3,3,'carbonation_model','Model','general_operating_v1','','','')")
    return conn


class CurrentModelContractTests(unittest.TestCase):
    def test_imported_unversioned_project_is_rejected_without_db_mutation(self):
        conn = project_database()
        raw = conn.execute('SELECT lca_settings_json FROM pathways WHERE id=1').fetchone()[0]
        with self.assertRaisesRegex(ValueError, 'Incompatible saved project #1'):
            get_project(conn, 1)
        self.assertEqual([item['id'] for item in list_projects(conn)], [6, 2])
        self.assertEqual(conn.execute('SELECT lca_settings_json FROM pathways WHERE id=1').fetchone()[0], raw)
        current, _, _ = get_project(conn, 2)
        self.assertEqual(current['lca_settings'], current_settings())
        self.assertNotIn('model_version', current)
        self.assertNotIn('historical_model', current)
        with self.assertRaisesRegex(ValueError, 'unsupported Carbonation model'):
            get_project(conn, 3)
        with self.assertRaisesRegex(ValueError, 'SCM delivery belongs in the recipe'):
            get_project(conn, 4)
        with self.assertRaisesRegex(ValueError, 'inbound waste transport moisture must be zero'):
            get_project(conn, 5)
        self.assertEqual(get_project(conn, 6)[0]['lca_settings']['transport']['waste_to_process']['moisture_percent'], 0)
        conn.close()

    def test_project_get_returns_422_and_list_filters_incompatible_import(self):
        conn = project_database()
        client = create_app().test_client()
        with patch('src.routes.project_routes.get_connection', return_value=conn):
            response = client.get('/api/v1/projects')
            self.assertEqual(response.status_code, 200)
            self.assertEqual([item['id'] for item in response.json], [6, 2])
            response = client.get('/api/v1/projects/1')
            self.assertEqual(response.status_code, 422)
            self.assertIn('Incompatible saved project #1', response.json['error'])
            response = client.get('/api/v1/projects/3')
            self.assertEqual(response.status_code, 422)
            self.assertIn('unsupported Carbonation model', response.json['error'])
            for project_id in (4, 5):
                response = client.get(f'/api/v1/projects/{project_id}')
                self.assertEqual(response.status_code, 422)
                self.assertIn('Incompatible saved project', response.json['error'])
        conn.close()

    def test_new_project_requires_exact_versions_and_current_carbonation(self):
        payload = dict(product_type='SCM', material=dict(material_name='slag'),
            processes=[dict(process_name='Grinding', parameters=[])],
            lca_settings=dict(electricity_scenario='E1'))
        valid, error = validate_project_payload(payload)
        self.assertFalse(valid)
        self.assertIn('current paired-energy', error)
        payload['lca_settings'] = current_settings()
        self.assertTrue(validate_project_payload(payload)[0])
        payload['lca_settings']['transport'] = {'waste_to_process': {'enabled': True, 'distance_km': 10, 'moisture_percent': 0}}
        self.assertTrue(validate_project_payload(payload)[0])
        payload['lca_settings']['transport']['waste_to_process']['moisture_percent'] = 5
        self.assertIn('inbound waste transport moisture must be zero', validate_project_payload(payload)[1])
        payload['lca_settings']['transport'] = {'scm_to_mix': {'enabled': False}}
        self.assertIn('SCM delivery belongs in the recipe', validate_project_payload(payload)[1])
        payload['lca_settings'] = current_settings()
        payload['processes'] = [dict(process_name='Carbonation', parameters=[
            dict(parameter_code='carbonation_model', value='unsupported_variant')])]
        valid, error = validate_project_payload(payload)
        self.assertFalse(valid)
        self.assertIn('unsupported Carbonation model', error)

    def test_calculation_endpoints_reject_unversioned_E1_before_engine(self):
        client = create_app().test_client()
        old = dict(lca_settings=dict(electricity_scenario='E1'), processes=[])
        with patch('src.routes.calculation_routes.calculate_project') as calculate:
            for endpoint in ('/api/v1/calculate', '/api/v1/calculate/export'):
                response = client.post(endpoint, json=old)
                self.assertEqual(response.status_code, 422)
                self.assertIn('Incompatible route', response.json['errors'][0])
                partial = client.post(endpoint, json=dict(
                    lca_settings=dict(model_version=2, electricity_scenario='E1'), processes=[]))
                self.assertEqual(partial.status_code, 422)
            calculate.assert_not_called()

    def test_imported_scm_snapshot_is_rejected_without_reading_old_factor(self):
        old = dict(pathway=dict(lca_settings=dict(electricity_scenario='E1')),
                   gwp_kg_co2e_kg=1.2345, method='old-method', boundary='old-boundary')
        row = dict(id='old-scm', name='Old SCM', density_kg_m3=2600,
                   snapshot_json=json.dumps(old), snapshot_hash='abc', created_at='2026-09-01')
        with self.assertRaisesRegex(ValueError, 'Incompatible saved scm material old-scm'):
            service.material(row)
        self.assertEqual(json.loads(row['snapshot_json']), old)
        current = dict(old, pathway=dict(lca_settings=current_settings()),
                       electricity_source=dict(unit='kilowatt hour'),
                       heat_source=dict(unit='megajoule'))
        with self.assertRaisesRegex(ValueError, 'paired-energy LCIA resolution'):
            service.material(dict(row, snapshot_json=json.dumps(dict(current, heat_source=None))))
        with self.assertRaisesRegex(ValueError, 'paired-energy LCIA resolution'):
            service.material(dict(row, snapshot_json=json.dumps(dict(current,
                transport=[dict(key='scm_to_mix', gwp=.25)]))))
        item = service.material(dict(row, snapshot_json=json.dumps(current)))
        self.assertNotIn('model_version', item)
        self.assertNotIn('historical_model', item)

    def test_old_scm_route_is_hidden_from_list_and_rejected_by_id(self):
        conn = sqlite3.connect(':memory:')
        conn.row_factory = sqlite3.Row
        conn.execute('CREATE TABLE scm_items (id TEXT,name TEXT,density_kg_m3 REAL,snapshot_json TEXT,snapshot_hash TEXT,created_at TEXT)')
        old = dict(pathway=dict(lca_settings=dict(electricity_scenario='E1')),
                   gwp_kg_co2e_kg=1, method='old-method', boundary='old-boundary')
        conn.execute('INSERT INTO scm_items VALUES (?,?,?,?,?,?)',
                     ('old-scm','Old SCM',2600,json.dumps(old),'abc','2026-09-01'))
        conn.execute('INSERT INTO scm_items VALUES (?,?,?,?,?,?)',
                     ('missing-settings','Missing settings',2600,
                      json.dumps(dict(old, pathway={})), 'def','2026-09-02'))
        client = create_app().test_client()
        with patch.object(service, 'get_connection', return_value=conn):
            self.assertEqual(service.list_materials(), [])
            response = client.get('/api/v1/scm-items/old-scm')
            self.assertEqual(response.status_code, 422)
            self.assertIn('Incompatible saved scm material', response.json['error'])
            response = client.get('/api/v1/scm-items/missing-settings')
            self.assertEqual(response.status_code, 422)
            self.assertIn('current LCA settings are required', response.json['error'])
        conn.close()

    def test_recipe_rejects_scm_snapshot_with_embedded_delivery(self):
        item = dict(snapshot=dict(transport=[dict(key='scm_to_mix', gwp=0.25)]))
        with self.assertRaisesRegex(ValueError, 'SCM delivery belongs in the recipe'):
            recipe_transport({}, item, 1, 1)
        delivery = recipe_transport({}, dict(snapshot=dict(transport=[])), 1, 1)
        self.assertFalse(delivery['included'])
        self.assertNotIn('removed_from_scm_factor_kg_co2e_kg', delivery)

    def test_imported_recipe_result_is_rejected_without_recalculation(self):
        conn = sqlite3.connect(':memory:')
        conn.row_factory = sqlite3.Row
        conn.execute('CREATE TABLE recipe_records (id TEXT,name TEXT,payload_json TEXT,result_json TEXT,created_at TEXT)')
        conn.execute('INSERT INTO recipe_records VALUES (?,?,?,?,?)',
            ('old-recipe','Old mix','{}','{"gwp_kg_co2e_m3":123.45}','2026-09-01'))
        with patch.object(service, 'get_connection', return_value=conn):
            with self.assertRaisesRegex(ValueError, 'Incompatible saved recipe old-recipe'):
                service.get_recipe('old-recipe')
            self.assertEqual(service.list_recipes(), [])
            current = dict(gwp_kg_co2e_m3=12.34, **current_settings())
            conn.execute('DELETE FROM recipe_records')
            conn.execute('INSERT INTO recipe_records VALUES (?,?,?,?,?)',
                ('current-recipe','Current mix','{}',json.dumps(current),'2026-10-15'))
            item = service.get_recipe('current-recipe')
            self.assertEqual(item['result'], current)
            self.assertNotIn('historical_model', item)
            self.assertEqual([item['id'] for item in service.list_recipes()], ['current-recipe'])
        conn.close()

    def test_new_recipe_result_records_current_versions(self):
        with patch.object(service, 'calculate_recipe', return_value=dict(ok=True, gwp_kg_co2e_m3=1)):
            result = service.calculate(dict())
        self.assertNotIn('model_version', result)
        self.assertEqual(result['energy_scenario_version'], ENERGY_SCENARIO_VERSION)
        self.assertEqual(result['input_defaults_version'], INPUT_DEFAULTS_VERSION)

    def test_numeric_model_marker_is_not_required_or_interpreted(self):
        settings = current_settings()
        self.assertEqual(require_current_settings(settings), settings)
        for marker in (1, 2, 999):
            with self.subTest(marker=marker):
                tagged = dict(settings, model_version=marker)
                self.assertEqual(require_current_settings(tagged), tagged)

    def test_saved_project_opens_without_numeric_model_marker(self):
        conn = project_database()
        settings = current_settings()
        raw = json.dumps(settings)
        conn.execute('UPDATE pathways SET lca_settings_json=? WHERE id=2', (raw,))
        pathway, _, _ = get_project(conn, 2)
        self.assertEqual(pathway['lca_settings'], settings)
        self.assertNotIn('model_version', pathway)
        self.assertEqual(conn.execute('SELECT lca_settings_json FROM pathways WHERE id=2').fetchone()[0], raw)
        conn.close()


if __name__ == '__main__':
    unittest.main()
