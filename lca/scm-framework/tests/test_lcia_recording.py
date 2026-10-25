"""Provider-record tests use synthetic identities; no licensed data is needed."""
import copy
import json
import unittest
from unittest.mock import patch

from src.recipes.recording import finalize_lcia_recording
from src.recipes.electricity_scenarios import ENERGY_SCENARIO_VERSION
from src.calculation.process_settings.carbonation import INPUT_DEFAULTS_VERSION


def provider(code='electricity', unit='kilowatt hour'):
    return dict(database='synthetic-test', code=code, name=f'Test {code}',
                location='XX', unit=unit, reference_product=code,
                id='local-only-id', factor=987654.321)


def records(fu=2):
    flows = ('electricity_kwh', 'heat_kwh', 'wastewater_treatment_kg', 'co2_stored_kg',
             'co2_emitted_kg', 'co2_makeup_kg', 'co2_makeup_loss_kg')
    return dict(route=dict(functional_unit_kg=fu), inputs=[dict(value=3)],
                A=dict(exchanges=[dict(native_quantity=7)]), B=dict(steps=[dict(scale=2)]),
                C=dict(status='unlinked_foreground', exchanges=[
                    dict(exchange_id=f'op-1:{flow}', flow_key=flow)
                    for flow in flows], provider_links=[]))


def resolution_data():
    return dict(settings=dict(model_version=2, energy_scenario_version=ENERGY_SCENARIO_VERSION,
                              input_defaults_version=INPUT_DEFAULTS_VERSION,
                              electricity_scenario='E0', co2_source='C1',
                              transport=dict(waste_to_process=dict(enabled=True, distance_km=100,
                                                                     moisture_percent=0))),
                processes=[dict(process_order=1, contributions=[
                    dict(flow='electricity_kwh', amount=3, unit='kilowatt hour',
                         provider=provider(), factor=987654.321),
                    dict(flow='heat_kwh', amount=3.6, unit='megajoule',
                         provider=provider('heat', 'megajoule'), factor=987654.321),
                    dict(flow='wastewater_treatment_kg', amount=-.001, unit='cubic meter',
                         provider=provider('wastewater', 'cubic meter')),
                    dict(flow='co2_emitted_kg', amount=.02, unit='kg'),
                    dict(flow='co2_stored_kg', amount=.1, unit='kg'),
                    dict(flow='co2_makeup_kg', amount=.12, unit='kg',
                         provider=dict(name='Authored source', location='Author inventory'))])],
                transport=[dict(key='waste_to_process', label='Waste delivery',
                                ton_km=.1, allocated_ton_km=.1, distance_km=100,
                                moisture_percent=0, provider=provider('freight', 'ton kilometer'))],
                source_components=[dict(kind='technosphere', amount=1, unit='kilogram',
                                        provider=provider('CO2', 'kilogram'), factor=987654.321)],
                electricity_source=provider(), heat_source=provider('heat', 'megajoule'),
                method=['synthetic', 'GWP'])


class LciaRecordTests(unittest.TestCase):
    def test_preserves_A_B_and_input_and_records_used_quantities(self):
        original = records()
        before = copy.deepcopy(original)
        actual = finalize_lcia_recording(original, **resolution_data())
        self.assertEqual(original, before)
        for stage in ('inputs', 'A', 'B'):
            self.assertEqual(actual[stage], before[stage])
        links = {row['flow_key']: row for row in actual['C']['provider_links']}
        self.assertEqual(links['electricity_kwh']['quantity'], 6)
        self.assertEqual(links['heat_kwh']['quantity'], 7.2)
        self.assertEqual(links['heat_kwh']['foreground_quantity'], 2)
        self.assertEqual(links['heat_kwh']['conversion_factor'], 3.6)
        self.assertEqual(actual['C']['energy_supply']['process_heat']['unit'], 'megajoule')
        self.assertEqual(links['wastewater_treatment_kg']['quantity'], -.002)
        self.assertEqual(links['waste_to_process']['quantity'], .2)
        self.assertNotIn('co2_makeup_loss_kg', links)
        self.assertIsNone(links['co2_stored_kg']['provider'])
        self.assertEqual(links['co2_makeup_kg']['source_inventory'], 'co2_supply_inventory')
        self.assertEqual(links['co2_makeup_kg']['source_inventory_scope'], 'same_resolution')
        self.assertEqual(actual['C']['co2_supply_inventory']['source'], 'C1')

    def test_record_excludes_scores_and_local_database_ids(self):
        serialized = json.dumps(finalize_lcia_recording(records(), **resolution_data()))
        self.assertNotIn('987654.321', serialized)
        self.assertNotIn('local-only-id', serialized)
        self.assertNotIn('co2_supply_factor', serialized)

    def test_derived_supply_is_not_claimed_as_database_activity(self):
        args = resolution_data()
        derived = dict(code='paper-E1', scenario='E1', name='Derived electricity',
                       location='DE', unit='kilowatt hour')
        args['settings']['electricity_scenario'] = 'E1'
        args['electricity_source'] = derived
        args['processes'][0]['contributions'][0]['provider'] = derived
        output = finalize_lcia_recording(records(1), **args)
        link = output['C']['provider_links'][0]
        self.assertEqual(link['status'], 'resolved_derived_supply')
        self.assertEqual(len(link['component_identities']), 4)
        self.assertNotIn('database', link['provider'])

    def test_source_inventory_is_recorded_as_authored_inventory(self):
        args = resolution_data()
        output = finalize_lcia_recording(records(), **args)
        self.assertEqual(output['C']['co2_supply_inventory']['status'], 'resolved_authored_inventory')

    def test_actual_calculation_preserves_results_with_recording(self):
        from src.recipes import calculation as calc
        payload = dict(functional_unit_kg=3, lca_settings=dict(model_version=2,
            energy_scenario_version=ENERGY_SCENARIO_VERSION,
            input_defaults_version=INPUT_DEFAULTS_VERSION), processes=[dict(
            process_name='Grinding', process_order=1,
            parameters=[dict(parameter_code=key, value=value) for key, value in
                        [('F80_um', 1000), ('P80_um', 200), ('Wi_value', 10)]])])
        providers = {key: provider(key, 'megajoule' if key == 'heat' else 'kilowatt hour')
                     for key, _ in calc.FLOW_MAP.values()}
        with patch.object(calc.bg, 'catalogue', return_value=dict(providers=providers)), \
                patch.object(calc.bg, 'sensitivity_energy', return_value=(provider(), None, provider('heat', 'megajoule'), None)), \
                patch.object(calc.bg, 'factors', side_effect=lambda rows: {row['code']: .5 for row in rows}), \
                patch.object(calc.bg, 'fingerprint', return_value='synthetic-test'):
            actual = calc.calculate_scm_lca(payload)
            with patch.object(calc, 'finalize_lcia_recording', side_effect=lambda value, **kwargs: value):
                without_link_recording = calc.calculate_scm_lca(payload)
        self.assertTrue(actual['ok'])
        self.assertEqual(actual['lca'], without_link_recording['lca'])
        self.assertEqual(actual['summary'], without_link_recording['summary'])
        self.assertEqual(actual['items'], without_link_recording['items'])
        resolution = actual['records']['C']['lcia_resolution']
        self.assertEqual(resolution['functional_unit_kg'], 1)
        self.assertEqual(resolution['basis'], 'per_kg_dry_SCM')
        link = next(row for row in resolution['provider_links']
                    if row['flow_key'] == 'electricity_kwh')
        self.assertAlmostEqual(link['quantity'] * payload['functional_unit_kg'],
                               actual['summary']['allocated_totals']['electricity_kwh'])
        self.assertEqual(actual['records']['C']['exchanges'],
                         without_link_recording['records']['C']['exchanges'])

    def test_carbonation_alias_and_authored_supply_record_actual_choices(self):
        from src.recipes import calculation as calc
        payload = dict(functional_unit_kg=4, processes=[dict(
            process_name='Carbonation', process_order=1,
            parameters=[dict(parameter_code=key, value=value) for key, value in [
                ('carbonation_model', 'general_operating_v2'), ('co2_uptake_kg', .1),
                ('t_reaction_h', 2),
                ('condition_inputs', dict(water_mode='wet', water_powder_ratio=2, gas_mode='none'))]])])
        providers = {key: provider(key, 'megajoule' if key == 'heat' else 'kilowatt hour')
                     for key, _ in calc.FLOW_MAP.values()}
        def exact(name, location, unit):
            return dict(provider(name, unit), location=location)
        for source in ('C0', 'C1', 'C2'):
            with self.subTest(source=source), \
                    patch.object(calc.bg, 'catalogue', return_value=dict(providers=providers)), \
                    patch.object(calc.bg, 'sensitivity_energy', return_value=(provider(), None, provider('heat', 'megajoule'), None)), \
                    patch.object(calc.bg, 'exact_activity', side_effect=exact), \
                    patch.object(calc.bg, 'exact_elementary', side_effect=lambda name, categories, unit: exact(name, 'biosphere', unit)), \
                    patch.object(calc.bg, 'factors', side_effect=lambda rows: {row['code']: .5 for row in rows}), \
                    patch.object(calc.bg, 'elementary_factors', side_effect=lambda rows: {row['code']: .5 for row in rows}), \
                    patch.object(calc.bg, 'fingerprint', return_value='synthetic-test'):
                payload['lca_settings'] = dict(model_version=2,
                    energy_scenario_version=ENERGY_SCENARIO_VERSION,
                    input_defaults_version=INPUT_DEFAULTS_VERSION, co2_source=source)
                actual = calc.calculate_scm_lca(payload)
                self.assertTrue(actual['ok'])
                rows = {row['flow_key']: row for row in actual['records']['C']['exchanges']}
                self.assertEqual(rows['co2_emitted_kg']['alias_of'], 'co2_makeup_loss_kg')
                self.assertFalse(rows['co2_emitted_kg']['included_in_physical_inventory'])
                self.assertFalse(rows['co2_stored_kg']['included_in_physical_inventory'])
                resolution = actual['records']['C']['lcia_resolution']
                links = {row['flow_key']: row for row in resolution['provider_links']}
                self.assertIn('co2_emitted_kg', links)
                self.assertIn('co2_stored_kg', links)
                self.assertNotIn('co2_makeup_loss_kg', links)
                self.assertEqual(resolution['co2_supply_inventory']['source'], source)
                self.assertEqual(len(resolution['co2_supply_inventory']['exchanges']),
                                 len(calc.CO2_SOURCES[source]['entries']) + len(calc.CO2_SOURCES[source]['elementary']))
                self.assertNotIn('987654.321', json.dumps(resolution))

    def test_process_heat_is_characterized_in_mj_once(self):
        from src.recipes import calculation as calc
        payload = dict(functional_unit_kg=1, lca_settings=dict(model_version=2,
            energy_scenario_version=ENERGY_SCENARIO_VERSION,
            input_defaults_version=INPUT_DEFAULTS_VERSION,
            electricity_scenario='E0', co2_source='C1'),
            processes=[dict(process_name='Carbonation', process_order=1,
                parameters=[dict(parameter_code=key, value=value) for key, value in [
                    ('carbonation_model', 'general_operating_v2'), ('co2_uptake_kg', .1),
                    ('t_reaction_h', 2), ('condition_inputs', dict(water_mode='wet',
                        water_powder_ratio=2, heat_up=True, target_temperature_C=70,
                        gas_mode='none', drying=True))]])])
        providers = {key: provider(key, 'megajoule' if key == 'heat' else 'kilowatt hour')
                     for key, _ in calc.FLOW_MAP.values()}
        factors = lambda rows: {row['code']: {'electricity': 2, 'heat': .1}.get(row['code'], 0)
                                for row in rows}
        with patch.object(calc.bg, 'catalogue', return_value=dict(providers=providers)), \
                patch.object(calc.bg, 'sensitivity_energy', return_value=(provider(), None,
                    provider('heat', 'megajoule'), None)), \
                patch.object(calc.bg, 'exact_activity', side_effect=lambda name, location, unit: dict(provider(name, unit), location=location)), \
                patch.object(calc.bg, 'factors', side_effect=factors), \
                patch.object(calc.bg, 'fingerprint', return_value='synthetic-test'):
            actual = calc.calculate_scm_lca(payload)
        self.assertTrue(actual['ok'])
        lca = actual['lca']
        self.assertGreater(lca['energy']['heat_kwh'], 0)
        self.assertAlmostEqual(lca['energy']['heat_mj'], lca['energy']['heat_kwh'] * 3.6)
        self.assertAlmostEqual(lca['energy']['electricity_gwp_kg_co2e'],
                               lca['energy']['electricity_kwh'] * 2)
        self.assertAlmostEqual(lca['energy']['heat_gwp_kg_co2e'],
                               lca['energy']['heat_mj'] * .1)
        heat_row = next(row for row in lca['contributions'] if row['flow'] == 'heat_kwh')
        self.assertEqual(heat_row['unit'], 'megajoule')
        self.assertAlmostEqual(heat_row['amount'], lca['energy']['heat_mj'])
        heat_link = next(row for row in actual['records']['C']['lcia_resolution']['provider_links']
                         if row['flow_key'] == 'heat_kwh')
        self.assertAlmostEqual(heat_link['foreground_quantity'], lca['energy']['heat_kwh'])

    def test_incompatible_route_is_rejected_without_recalculation(self):
        from src.recipes import calculation as calc
        for settings in ({'model_version': 1, 'electricity_scenario': 'E1'}, {}):
            with self.subTest(settings=settings), self.assertRaisesRegex(ValueError, 'Incompatible route'):
                calc.scm_foreground(dict(project_id=41, lca_settings=settings, processes=[]))
        with self.assertRaisesRegex(ValueError, 'Incompatible route'):
            calc.calculate_scm_lca(dict(lca_settings=dict(electricity_scenario='E1'), processes=[]))
        with self.assertRaisesRegex(ValueError, 'Incompatible route'):
            calc.calculate_scm_lca(dict(lca_settings=dict(model_version=2), processes=[]))
        with self.assertRaisesRegex(ValueError, 'Incompatible route'):
            calc.calculate_scm_lca(dict(lca_settings=dict(model_version=2,
                energy_scenario_version=ENERGY_SCENARIO_VERSION), processes=[]))

    def test_supplied_CO2_factor_is_rejected(self):
        from src.recipes import calculation as calc
        with self.assertRaisesRegex(ValueError, 'supplied CO2 factor is unsupported'):
            calc.lca_settings(dict(lca_settings=dict(model_version=2,
                energy_scenario_version=ENERGY_SCENARIO_VERSION,
                input_defaults_version=INPUT_DEFAULTS_VERSION,
                co2_source='C0', co2_supply_factor=0.01)))

    def test_paired_scenario_rejects_independent_heat_provider(self):
        from src.recipes import calculation as calc
        with self.assertRaisesRegex(ValueError, 'one E0/E1/E2 choice'):
            calc.lca_settings(dict(lca_settings=dict(model_version=2,
                energy_scenario_version=ENERGY_SCENARIO_VERSION,
                input_defaults_version=INPUT_DEFAULTS_VERSION,
                electricity_scenario='E0', heat_code='arbitrary-market')))

    def test_scm_route_transport_rejects_delivery_and_wet_cargo(self):
        from src.recipes import calculation as calc
        base = dict(model_version=2, energy_scenario_version=ENERGY_SCENARIO_VERSION,
                    input_defaults_version=INPUT_DEFAULTS_VERSION, electricity_scenario='E0')
        valid = dict(base, transport=dict(waste_to_process=dict(
            enabled=True, distance_km=10, moisture_percent=0)))
        self.assertEqual(calc.lca_settings(dict(lca_settings=valid)), valid)
        for transport, error in (
            (dict(scm_to_mix=dict(enabled=False)), 'SCM delivery belongs in the recipe'),
            (dict(waste_to_process=dict(enabled=True, distance_km=10,
                                        moisture_percent=5)), 'inbound waste transport moisture must be zero')):
            with self.subTest(transport=transport), self.assertRaisesRegex(ValueError, error):
                calc.lca_settings(dict(lca_settings=dict(base, transport=transport)))


if __name__ == '__main__':
    unittest.main()
