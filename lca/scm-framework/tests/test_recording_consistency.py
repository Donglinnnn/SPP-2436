"""Check A–B–C source records against current foreground calculations."""

import json
import math
from pathlib import Path
import unittest

from src.calculation.engine import run_calculation


FIXTURE_PATH = Path(__file__).with_name("fixtures") / "current_route_requests.json"


def route_cases():
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))["cases"]


class RecordingConsistencyTests(unittest.TestCase):
    def test_current_routes_calculate_with_records(self):
        for case in route_cases():
            with self.subTest(case=case["name"]):
                response = run_calculation(case["request"]).to_dict()
                self.assertTrue(response["ok"], response["errors"])
                self.assertIn("records", response)
                self.assertEqual(response["records"]["C"]["status"], "unlinked_foreground")

    def test_recorded_bases_reconcile_to_process_inventories(self):
        for case in route_cases():
            response = run_calculation(case["request"])
            self.assertTrue(response.ok, response.errors)
            for item in response.items:
                record = item.metadata["recording"]
                for flow_key, row in record["exchange_metadata"].items():
                    with self.subTest(case=case["name"], process=item.process_order, flow=flow_key):
                        native = row.get("native_quantity", record["native_inventory"].get(flow_key))
                        factor = row.get("normalization_factor_to_process_product",
                                         record["normalization_factor_to_process_product"])
                        self.assertIsNotNone(native)
                        self.assertTrue(math.isclose(native * factor,
                                                     item.metadata["inventory"][flow_key],
                                                     rel_tol=1e-12, abs_tol=1e-15))

    def test_generation_layer_and_input_provenance(self):
        cases = {case["name"]: case for case in route_cases()}
        grinding = run_calculation(cases["grinding_input_basis"]["request"])
        self.assertTrue(grinding.ok, grinding.errors)
        rows = grinding.items[0].metadata["recording"]["exchange_metadata"]
        self.assertEqual(rows["electricity_kwh"]["generation_layer"], "L1")
        self.assertIsNone(rows["grinding_machine_kg"]["generation_layer"])
        record = grinding.to_dict()["records"]
        ids = {row["parameter_id"] for row in record["inputs"]}
        for row in record["A"]["exchanges"]:
            self.assertTrue(set(row["parameter_refs"]).issubset(ids), row["exchange_id"])
        f80 = next(row for row in record["inputs"] if row["parameter_id"] == "op-1:F80_um")
        self.assertEqual(f80["effective"]["provenance"], "ASM")
        self.assertEqual(f80["effective"]["source_note"],
                         "Synthetic test input; not an experimental claim.")

        crushing = run_calculation(cases["crushing_fixed_inventory"]["request"])
        self.assertTrue(crushing.ok, crushing.errors)
        rows = crushing.items[0].metadata["recording"]["exchange_metadata"]
        self.assertIsNone(rows["diesel_burned_mj"]["generation_layer"])
        self.assertEqual(rows["upstream_input_kg"]["generation_layer"], "L1")


if __name__ == "__main__":
    unittest.main()
