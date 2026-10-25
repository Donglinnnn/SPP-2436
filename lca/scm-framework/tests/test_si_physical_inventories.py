"""SI equipment and sorting quantities keep their declared product mass basis."""

import unittest

from src.calculation.engine import run_calculation
from src.calculation.modules.grinding import calculate_grinding
from src.calculation.parameters import calculation_schema
from src.calculation.schemas import ProcessInput, ProcessParameterRecord
from src.calculation.supporting_data.infrastructure import GRINDING_MACHINE_SOURCE


def process(name, **values):
    return dict(process_name=name, process_order=1, parameters=[
        dict(parameter_code=key, value=str(value), unit="") for key, value in values.items()])


def route(name, **values):
    return run_calculation(dict(pathway_name="SI inventory checks", functional_unit_kg=3,
                                processes=[process(name, **values)]))


def grinding_result(**values):
    rows = [ProcessParameterRecord(key, key, str(value), "") for key, value in
            dict(F80_um=1000, P80_um=200, Wi_value=12, **values).items()]
    return calculate_grinding(ProcessInput("Grinding", 1, rows))


class SIPhysicalInventoryTests(unittest.TestCase):
    def test_sorting_inventory_per_product_with_recovery_and_allocation(self):
        result = route("Sorting", input_mass_kg=10, output_mass_kg=8,
                       coproduct_fraction=.5, allocation_method="mass")
        self.assertTrue(result.ok, result.errors)
        totals = result.summary["totals"]
        self.assertAlmostEqual(totals["diesel_burned_mj"], .00437 * 3)
        self.assertAlmostEqual(totals["hydraulic_digger_m3"], .000353 * 3)
        factor = 1 / (1 + (.25 * .5))
        self.assertAlmostEqual(result.summary["allocated_totals"]["diesel_burned_mj"], .00437 * 3 * factor)
        rows = result.items[0].metadata["recording"]["exchange_metadata"]
        self.assertIn("SI1-3_ParameterAndInventories.xlsx", rows["diesel_burned_mj"]["source_reference"])

    def test_grinding_default_per_product_not_scaled_again_by_feed_yield(self):
        schema = calculation_schema()["processes"]["Grinding"]["parameters"]
        self.assertEqual(schema["grinding_machine_kg_per_kg_product"]["default"], 4.41e-7)
        for energy_basis in ("processed_input", "target_output"):
            with self.subTest(energy_basis=energy_basis):
                result = route("Grinding", F80_um=1000, P80_um=200, Wi_value=12,
                               yield_fraction=.8, inventory_basis=energy_basis,
                               coproduct_fraction=.5, allocation_method="mass")
                self.assertTrue(result.ok, result.errors)
                self.assertAlmostEqual(result.summary["totals"]["grinding_machine_kg"], 4.41e-7 * 3)
                self.assertAlmostEqual(result.summary["allocated_totals"]["grinding_machine_kg"],
                                       4.41e-7 * 3 / 1.125)
                row = result.items[0].metadata["recording"]["exchange_metadata"]["grinding_machine_kg"]
                self.assertEqual(row["native_basis"], "per kg dry process product")
                self.assertEqual(row["normalization_factor_to_process_product"], 1)
                self.assertEqual(row["source_reference"], GRINDING_MACHINE_SOURCE)

    def test_explicit_equipment_overrides_retain_their_own_basis(self):
        for key, coefficient, expected in (
            ("grinding_machine_kg_per_kg_product", 9e-7, 9e-7),
            ("grinding_machine_kg_per_kg_product", 0, 0),
            ("grinding_machine_kg_per_kg_processed", 9e-7, 9e-7 / .8),
            ("grinding_machine_kg_per_kg_processed", 0, 0),
        ):
            with self.subTest(key=key, coefficient=coefficient):
                result = grinding_result(yield_fraction=.8, **{key: coefficient})
                self.assertAlmostEqual(result.metadata["inventory"]["grinding_machine_kg"], expected)
                if key.endswith("processed"):
                    inactive = result.metadata["parameters"]["grinding_machine_kg_per_kg_product"]
                    self.assertEqual(inactive["origin"], "not_used")
                    self.assertIsNone(inactive["value"])

    def test_conflicting_explicit_equipment_bases_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "Supply one grinding equipment basis"):
            grinding_result(grinding_machine_kg_per_kg_product=4.41e-7,
                            grinding_machine_kg_per_kg_processed=4.41e-7)


if __name__ == "__main__":
    unittest.main()
