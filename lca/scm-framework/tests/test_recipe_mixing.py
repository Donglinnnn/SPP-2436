"""Foam inventory scaling and result construction with synthetic providers."""
import unittest
from unittest.mock import patch

from src.recipes import calculation as calc
from src.recipes import service


class FoamMixingTests(unittest.TestCase):
    def test_reference_mass_and_machine_conversion_survive_reference_comparison(self):
        providers = {
            key: dict(code=key, name=key, location='XX', unit='kilogram')
            for key in ('cement', 'sand', 'aggregate', 'water', 'electricity', 'machine')
        }
        providers['electricity']['unit'] = 'kilowatt hour'
        factors = dict(cement=.7, water=.0001, electricity=.5, machine=1)
        cases = [
            ({}, 1000, .41, .00146, .20646),
            ({'foam_reference_mass_kg': 500, 'foam_machine_kg_per_unit': 1000},
             500, .82, .00146, .41146),
            ({'basis': 'batch', 'volume_mode': 'measured', 'measured_volume_m3': 2},
             1000, .205, .00073, .10323),
        ]
        with patch.object(calc.bg, 'catalogue', return_value={
                'providers': providers, 'cements': [providers['cement']]}), \
                patch.object(calc.bg, 'factors', side_effect=lambda rows: {
                    row['code']: factors[row['code']] for row in rows}), \
                patch.object(calc.bg, 'fingerprint', return_value='synthetic-test'):
            for overrides, reference_mass, electricity, machine, gwp in cases:
                with self.subTest(overrides=overrides):
                    result = service.calculate(dict(
                        specimen_class='foam_concrete', preparation_mode='foam',
                        amounts=dict(cement=600, water=400), **overrides))
                    self.assertTrue(result['ok'])
                    preparation = result['preparation']
                    self.assertEqual(preparation['reference_mass_kg'], reference_mass)
                    self.assertAlmostEqual(preparation['electricity_kwh_m3'], electricity)
                    self.assertAlmostEqual(preparation['machine_kg_m3'], machine)
                    self.assertAlmostEqual(preparation['gwp_kg_co2e_m3'], gwp)
                    self.assertIsNone(result['reference_concrete'])
                    self.assertEqual(preparation['reference_mass_status'], 'unverified')
                    self.assertTrue(any(f'({reference_mass:g} kg;' in warning
                                        for warning in result['warnings']))


if __name__ == '__main__':
    unittest.main()
