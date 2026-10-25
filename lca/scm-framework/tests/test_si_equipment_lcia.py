"""SI equipment quantities survive route scaling and reach their LCIA suppliers.

Background identities and factors are synthetic: these tests exercise the actual
foreground and LCIA entry points without requiring licensed database access.
"""

from contextlib import ExitStack, contextmanager
import copy
import unittest
from unittest.mock import patch

from src.calculation.process_settings.carbonation import INPUT_DEFAULTS_VERSION
from src.recipes import calculation as calc
from src.recipes.electricity_scenarios import ENERGY_SCENARIO_VERSION


def process(name, order, **values):
    return dict(process_name=name, process_order=order, parameters=[
        dict(parameter_code=key, value=value) for key, value in values.items()
    ])


def route(processes, functional_unit_kg):
    return dict(functional_unit_kg=functional_unit_kg, processes=processes,
                lca_settings=dict(energy_scenario_version=ENERGY_SCENARIO_VERSION,
                                  input_defaults_version=INPUT_DEFAULTS_VERSION,
                                  electricity_scenario="E0", co2_source="C1"))


def provider(code, unit):
    return dict(database="synthetic-test", code=code, name=f"Synthetic {code}",
                location="XX", unit=unit, reference_product=code)


@contextmanager
def background(factors):
    units = dict(electricity="kilowatt hour", heat="megajoule", water="kilogram",
                 wastewater="cubic meter", diesel="megajoule", machine="kilogram",
                 digger="cubic meter", sorting="unit", thermal_factory="unit",
                 carbonation_factory="unit")
    providers = {key: provider(key, unit) for key, unit in units.items()}
    with ExitStack() as stack:
        stack.enter_context(patch.object(calc.bg, "catalogue", return_value=dict(providers=providers)))
        stack.enter_context(patch.object(calc.bg, "sensitivity_energy", return_value=(
            providers["electricity"], None, providers["heat"], None)))
        stack.enter_context(patch.object(calc.bg, "exact_activity", side_effect=
            lambda name, location, unit: dict(provider(name, unit), location=location)))
        score = stack.enter_context(patch.object(calc.bg, "factors", side_effect=
            lambda rows: {row["code"]: factors.get(row["code"], 0) for row in rows}))
        stack.enter_context(patch.object(calc.bg, "fingerprint", return_value="synthetic-equipment-test"))
        yield score


class SiEquipmentLciaTests(unittest.TestCase):
    def assert_quantity(self, actual, expected):
        # Absolute decimal-place comparisons would silently accept zero for the
        # small factory coefficients; compare their ratio instead.
        self.assertGreater(expected, 0)
        self.assertAlmostEqual(actual / expected, 1, places=12)

    def test_sorting_and_grinding_follow_product_basis_and_downstream_allocation(self):
        payload = route([
            process("Sorting", 1, input_mass_kg=1, output_mass_kg=.5),
            process("Grinding", 2, F80_um=1000, P80_um=200, Wi_value=10,
                    yield_fraction=.8, coproduct_fraction=1, allocation_method="mass"),
        ], functional_unit_kg=4)
        before = copy.deepcopy(payload)
        with background(dict(diesel=10, digger=20, machine=30)):
            actual = calc.calculate_scm_lca(payload)
        self.assertEqual(payload, before)
        self.assertTrue(actual["ok"], actual.get("errors"))
        summary = actual["summary"]
        # Four kg grinding product requires five kg sorting product and ten kg
        # original feed. Grinding equipment is per product, so not multiplied
        # by grinding's 1/0.8 input requirement. Sorting's default is also per
        # target product, so its own 1/0.5 yield must not rescale the SI values.
        self.assert_quantity(summary["initial_feed_required_kg"], 10)
        physical = dict(diesel_burned_mj=.00437 * 5,
                        hydraulic_digger_m3=.000353 * 5,
                        grinding_machine_kg=4.41e-7 * 4)
        for flow, expected in physical.items():
            with self.subTest(flow=flow):
                self.assert_quantity(summary["totals"][flow], expected)
                self.assert_quantity(summary["allocated_totals"][flow], expected * .8)
        rows = {row["flow"]: row for row in actual["lca"]["contributions"]}
        for flow, supplier, factor in (("diesel_burned_mj", "diesel", 10),
                                       ("hydraulic_digger_m3", "digger", 20),
                                       ("grinding_machine_kg", "machine", 30)):
            with self.subTest(supplier=supplier):
                self.assertEqual(rows[flow]["provider"]["code"], supplier)
                self.assert_quantity(rows[flow]["amount"], physical[flow] * .8 / 4)
                self.assert_quantity(rows[flow]["gwp"], physical[flow] * .8 / 4 * factor)
        expected_total = (.00437 * 5 * 10 + .000353 * 5 * 20 + 4.41e-7 * 4 * 30) * .8
        self.assert_quantity(actual["lca"]["gwp_kg_co2e"], expected_total)

    def test_factory_units_are_scaled_once_and_link_to_distinct_suppliers(self):
        payload = route([
            process("Thermal activation", 1, activation_temperature_C=550, holding_time_h=2,
                    tga_intervals_table=[dict(name="water loss", start_C=30, end_C=105,
                                             loss_fraction=.1, h2o_share=1, co2_share=0)]),
            process("Carbonation", 2, carbonation_model="general_operating_v2",
                    co2_uptake_kg=.2, t_reaction_h=3,
                    condition_inputs=dict(water_mode="dry", gas_mode="none")),
        ], functional_unit_kg=5)
        factors = dict(thermal_factory=1e12, carbonation_factory=2e12)
        with background(factors) as score:
            actual = calc.calculate_scm_lca(payload)
            requested_suppliers = {row["code"] for call in score.call_args_list for row in call.args[0]}
        with background({}):
            without_factory_burden = calc.calculate_scm_lca(payload)
        self.assertTrue(actual["ok"], actual.get("errors"))
        self.assertTrue(without_factory_burden["ok"], without_factory_burden.get("errors"))
        self.assertEqual(actual["items"], without_factory_burden["items"])
        self.assertIn("thermal_factory", requested_suppliers)
        self.assertIn("carbonation_factory", requested_suppliers)
        self.assert_quantity(actual["summary"]["initial_feed_required_kg"], 5 / 1.2 / .9)
        expected = {
            "thermal_factory_unit": (4.029e-14 * 2 * 5 / 1.2, "thermal_factory"),
            "carbonation_factory_unit": (4.029e-13 * 3 * 5, "carbonation_factory"),
        }
        records = actual["records"]
        final = {row["flow_key"]: row for row in records["C"]["exchanges"]
                 if row["flow_key"] in expected}
        links = {row["flow_key"]: row for row in records["C"]["lcia_resolution"]["provider_links"]}
        contributions = {row["flow"]: row for row in actual["lca"]["contributions"]}
        for flow, (quantity, supplier) in expected.items():
            with self.subTest(flow=flow):
                self.assert_quantity(actual["summary"]["totals"][flow], quantity)
                row = final[flow]
                self.assertEqual(row["unit"], "unit")
                self.assertEqual(row["exchange_type"], "technosphere")
                self.assertTrue(row["included_in_physical_inventory"])
                self.assert_quantity(row["quantity"], quantity)
                self.assert_quantity(row["native_quantity"] * row["normalization_factor_to_process_product"],
                                     row["process_quantity"])
                self.assert_quantity(row["process_quantity"] * row["route_scaling_factor"], quantity)
                self.assertEqual(contributions[flow]["unit"], "unit")
                self.assert_quantity(contributions[flow]["amount"], quantity / 5)
                self.assert_quantity(contributions[flow]["gwp"], quantity / 5 * factors[supplier])
                self.assertEqual(links[flow]["provider"]["code"], supplier)
                self.assertEqual(links[flow]["unit"], "unit")
                self.assert_quantity(links[flow]["quantity"], quantity / 5)
                self.assertEqual(links[flow].get("conversion_factor", 1), 1)
        incremental_gwp = sum(quantity * factors[supplier] for quantity, supplier in expected.values())
        self.assert_quantity(actual["lca"]["gwp_kg_co2e"]
                             - without_factory_burden["lca"]["gwp_kg_co2e"], incremental_gwp)


if __name__ == "__main__":
    unittest.main()
