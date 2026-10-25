import copy
import csv
import io
import json
import unittest

from src.calculation.engine import run_calculation
from src.calculation.recording import export_record_csv, export_record_json
from src.recipes.electricity_scenarios import ENERGY_SCENARIO_VERSION
from src.calculation.process_settings.carbonation import INPUT_DEFAULTS_VERSION


def example_request():
    return dict(pathway_name="Example grinding", functional_unit_kg=3, processes=[dict(
        process_name="Grinding", process_order=1,
        parameters=[dict(parameter_code=key, value=value, unit=unit,
                         provenance="EXP" if key == "F80_um" else None,
                         source_note="Synthetic test input" if key == "F80_um" else None)
                    for key, value, unit in (
                        ("F80_um", 2, "mm"), ("P80_um", 250, "um"),
                        ("Wi_value", 13.6, "kWh/t"), ("yield_fraction", .8, "fraction"),
                        ("coproduct_fraction", .5, "fraction"), ("allocation_method", "mass", ""),
                        ("grinding_machine_kg_per_kg_processed", 4.41e-7, "kg/kg"))])])


class RecordExportTests(unittest.TestCase):
    def test_supplied_effective_provenance_and_allocation(self):
        payload = example_request()
        before = copy.deepcopy(payload)
        response = run_calculation(payload)
        self.assertTrue(response.ok, response.errors)
        self.assertEqual(payload, before)
        record = response.records
        params = {row["parameter_code"]: row for row in record["inputs"]}
        self.assertEqual(params["F80_um"]["supplied"][0]["unit"], "mm")
        self.assertEqual(params["F80_um"]["effective"]["value"], 2000)
        self.assertEqual(params["F80_um"]["effective"]["provenance"], "EXP")
        self.assertEqual(params["auxiliaries_factor"]["effective"]["origin"], "model_default")
        self.assertIsNone(params["auxiliaries_factor"]["effective"]["provenance"])
        rows = {row["flow_key"]: row for row in record["C"]["exchanges"]}
        self.assertAlmostEqual(rows["grinding_machine_kg"]["quantity"], 4.41e-7 * 3 / .8)
        self.assertLess(rows["electricity_kwh"]["allocated_quantity"], rows["electricity_kwh"]["quantity"])
        self.assertFalse(rows["upstream_input_kg"]["included_in_physical_inventory"])
        self.assertIsNone(rows["upstream_input_kg"]["allocated_quantity"])
        self.assertEqual(record["B"]["physical_totals"], response.summary["totals"])
        self.assertEqual(record, run_calculation(payload).records)

    def test_partial_route_does_not_claim_a_complete_inventory(self):
        payload = example_request()
        payload["processes"].append(dict(process_name="Drying", process_order=2))
        response = run_calculation(payload)
        self.assertFalse(response.ok)
        self.assertEqual(response.records["C"]["status"], "incomplete")
        self.assertEqual(response.records["C"]["exchanges"], [])
        self.assertEqual(response.records["A"]["operations"][1]["status"], "not_calculated")
        self.assertTrue(response.records["A"]["exchanges"])

    def test_json_and_csv_roundtrip_and_inert_text(self):
        record = run_calculation(example_request()).records
        self.assertEqual(json.loads(export_record_json(record)), record)
        for table in ("inputs", "A", "B", "C"):
            rows = list(csv.DictReader(io.StringIO(export_record_csv(record, table))))
            self.assertTrue(rows)
            self.assertEqual(rows[0]["run_id"], record["run_id"])
        record["C"]["exchanges"][0]["flow_name"] = "=1+1"
        rows = list(csv.DictReader(io.StringIO(export_record_csv(record))))
        self.assertEqual(rows[0]["flow_name"], "'=1+1")
        with self.assertRaises(ValueError):
            export_record_csv(record, "unknown")

    def test_api_export_works_for_both_api_prefixes(self):
        from src.application import create_app
        client = create_app().test_client()
        api_request = example_request()
        api_request['lca_settings'] = {'model_version': 2,
                                       'energy_scenario_version': ENERGY_SCENARIO_VERSION,
                                       'input_defaults_version': INPUT_DEFAULTS_VERSION}
        for prefix in ("/api", "/api/v1"):
            response = client.post(prefix + "/calculate/export", json=api_request)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json["schema_version"], "1.0")
            self.assertIn("attachment", response.headers["Content-Disposition"])
            csv_response = client.post(prefix + "/calculate/export?format=csv&table=inputs", json=api_request)
            self.assertEqual(csv_response.status_code, 200)
            self.assertIn("parameter_id", csv_response.text)
            self.assertEqual(client.post(prefix + "/calculate/export?format=other", json=api_request).status_code, 400)
            self.assertEqual(client.post(prefix + "/calculate/export?format=csv&table=other", json=api_request).status_code, 400)
            self.assertEqual(client.post(prefix + "/calculate/export", json={}).status_code, 422)

    def test_nonfinite_descriptive_metadata_does_not_break_calculation(self):
        payload = example_request()
        payload["material"] = {"note": float("inf")}
        response = run_calculation(payload)
        self.assertTrue(response.ok, response.errors)
        exported = json.loads(export_record_json(response.records))
        self.assertEqual(exported["route"]["material"]["note"], {"non_finite_number": "inf"})
        self.assertEqual(response.summary, run_calculation(example_request()).summary)


if __name__ == "__main__":
    unittest.main()
