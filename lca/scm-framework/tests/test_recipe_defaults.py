"""Browser-schema defaults and omitted-input calculation stay equivalent."""
from contextlib import ExitStack
import unittest
from unittest.mock import patch

from src.application import create_app
from src.recipes import background, service


class RecipeDefaultsTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        providers = {key: dict(code=key, name=key, location='XX', unit='kilogram')
                     for key in ('cement', 'sand', 'aggregate', 'water', 'electricity', 'machine')}
        providers['electricity']['unit'] = 'kilowatt hour'
        for name, value in {
            'catalogue': dict(providers=providers, cements=[providers['cement']]),
            'preparation_status': dict(available=True),
            'preparation_gwp': dict(gwp_kg_co2e_m3=7.5),
            'fingerprint': 'synthetic-test',
            'concrete_references': [],
            'lca_catalogue': dict(transport=[], defaults=dict(transport_code='test')),
        }.items():
            self.stack.enter_context(patch.object(background, name, return_value=value))
        self.stack.enter_context(patch.object(background, 'factors', side_effect=lambda rows: {
            row['code']: .5 for row in rows}))
        self.app = create_app()
        self.client = self.app.test_client()

    def test_schema_defaults_and_omitted_inputs_produce_same_results(self):
        response = self.client.get('/api/v1/recipe-schema')
        self.assertEqual(response.status_code, 200)
        schema = response.get_json()
        for kind in ('paste', 'foam_concrete'):
            for basis in ('per_m3', 'batch'):
                with self.subTest(kind=kind, basis=basis):
                    payload = dict(specimen_class=kind, basis=basis,
                                   amounts=dict(cement=600, water=400))
                    if kind == 'foam_concrete':
                        payload['preparation_mode'] = 'foam'
                    explicit = dict(schema['input_defaults'], **{
                        'densities': schema['default_densities'], **payload})
                    self.assertEqual(service.calculate(payload), service.calculate(explicit))
        # Omitted ingredient quantities must not turn into the browser starter mix.
        with self.assertRaisesRegex(ValueError, 'binder .* and recipe water are required'):
            service.calculate(dict(specimen_class='paste'))

    def test_custom_volume_inputs_override_defaults(self):
        result = service.calculate(dict(
            specimen_class='paste', basis='batch', preparation_mode='none',
            amounts=dict(cement=600, water=400),
            densities=dict(cement=3000, water=1000), air_percent=20))
        self.assertAlmostEqual(result['batch_volume_m3'], .75)
        self.assertAlmostEqual(result['gwp_kg_co2e_m3'], 500 / .75)


if __name__ == '__main__':
    unittest.main()
