"""Paired energy-provider selection without requiring a licensed local database."""

import unittest
from unittest.mock import patch

from src.recipes import background as bg
from src.recipes.electricity_scenarios import DELIVERY_CODES, SCENARIOS


def _exact(name, location, unit):
    return dict(code=f'{name}@{location}', name=name, location=location, unit=unit,
                reference_product='electricity' if unit == 'kilowatt hour' else 'heat')


class PairedEnergyScenarioTests(unittest.TestCase):
    def test_e0_e2_resolve_exact_electricity_and_megajoule_heat_markets(self):
        for scenario in ('E0', 'E2'):
            with self.subTest(scenario=scenario), \
                    patch.object(bg, 'exact_activity', side_effect=_exact) as exact, \
                    patch.object(bg, 'activity', side_effect=AssertionError('derived chain not expected')):
                electricity, electric_factor, heat, heat_factor = bg.sensitivity_energy(scenario)
            definition = SCENARIOS[scenario]
            self.assertIsNone(electric_factor)
            self.assertIsNone(heat_factor)
            self.assertEqual(electricity['name'], definition['name'])
            self.assertEqual(electricity['location'], definition['location'])
            self.assertEqual(heat['name'], definition['heat_name'])
            self.assertEqual(heat['location'], definition['heat_location'])
            self.assertEqual(heat['unit'], 'megajoule')
            self.assertEqual(exact.call_count, 2)
            exact.assert_any_call(definition['name'], definition['location'], 'kilowatt hour')
            exact.assert_any_call(definition['heat_name'], definition['heat_location'], 'megajoule')

    def test_e1_uses_validated_lignite_delivery_factor_with_separate_heat(self):
        def delivery(code):
            name = DELIVERY_CODES.get(code, SCENARIOS['E1']['generation_name'])
            return dict(code=code, name=name, location='DE', unit='kilowatt hour')

        with patch.object(bg, 'exact_activity', side_effect=_exact) as exact, \
                patch.object(bg, 'activity', side_effect=delivery) as activity:
            electricity, electric_factor, heat, heat_factor = bg.sensitivity_energy('E1')
        self.assertEqual(electricity['code'], 'paper-E1')
        self.assertEqual(electric_factor, 1.2934014829335918)
        self.assertIsNone(heat_factor)
        self.assertEqual(heat['unit'], 'megajoule')
        self.assertEqual(heat['name'], 'market for heat, district or industrial, other than natural gas')
        exact.assert_called_once_with(SCENARIOS['E1']['heat_name'],
                                      SCENARIOS['E1']['heat_location'], 'megajoule')
        self.assertEqual(activity.call_count, len(DELIVERY_CODES) + 1)
        activity.assert_any_call(SCENARIOS['E1']['generation_code'])

    def test_e1_rejects_a_changed_delivered_electricity_chain(self):
        with patch.object(bg, 'exact_activity', side_effect=_exact), \
                patch.object(bg, 'activity', return_value=dict(name='wrong', location='DE', unit='kilowatt hour')):
            with self.assertRaisesRegex(bg.BackgroundUnavailable, 'delivery chain differs'):
                bg.sensitivity_energy('E1')

    def test_default_heat_is_a_market(self):
        self.assertEqual(bg.DEFAULT_PROVIDERS['heat'],
                         ('market for heat, district or industrial, natural gas',
                          'Europe without Switzerland'))


if __name__ == '__main__':
    unittest.main()
