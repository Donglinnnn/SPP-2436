"""Core regression checks for the current carbonation energy and loading model."""

import json
from dataclasses import replace
from math import log
import unittest

from src.calculation.engine import run_calculation
from src.calculation.modules.general_conditions_carbonation import calculate_general_conditions
from src.calculation.models.retained_carbonation import GeneralCarbonationProcess
from src.calculation.parameters import calculation_schema
from src.calculation.process_settings.carbonation import (
    CarbonationMaterialSettings, CarbonationProcessSettings,
)
from src.calculation.schemas import ProcessInput, ProcessParameterRecord


def carbonation_input(variant, conditions, *, uptake=0.1, reaction_time=1):
    rows = [
        ("carbonation_model", variant, ""),
        ("co2_uptake_kg", str(uptake), "kg/kg solid"),
        ("t_reaction_h", str(reaction_time), "h"),
        ("condition_inputs", json.dumps(conditions), ""),
    ]
    return ProcessInput(
        "Carbonation", 1,
        [ProcessParameterRecord(code, code, value, unit) for code, value, unit in rows],
    )


class CarbonationEnergyAndLoadingTests(unittest.TestCase):
    def test_p3_includes_makeup_compression_without_batch_mass_divisor(self):
        expected_makeup = ((0.1 / 0.9) / 0.04401 * 8.31446261815324 * 293.15
                           * log(200000 / 101325) / 0.7 / 3_600_000)
        for loading in (150, 300):
            with self.subTest(loading=loading):
                result = calculate_general_conditions(carbonation_input("general_operating_v2", {
                    "water_mode": "dry", "pressurize": True, "target_pressure_bar": 2,
                    "background_overrides": {"chamber_loading_kg_per_m3": loading},
                }))
                components = result.metadata["details"]["electricity_components_kwh_per_kg_dry_input"]
                batch = 10 * loading
                expected_head = (200000 * (10 - batch / 2600) * log(200000 / 101325)
                                 / 0.7 / 3_600_000 / batch)
                self.assertAlmostEqual(components["headspace_pressurization"], expected_head)
                self.assertAlmostEqual(components["co2_makeup_compression"], expected_makeup)
                self.assertAlmostEqual(result.metadata["inventory"]["electricity_kwh"],
                                       (expected_head + expected_makeup) / 1.1)

        result = calculate_general_conditions(carbonation_input("general_operating_v2", {
            "water_mode": "dry", "pressurize": False, "target_pressure_bar": 2,
        }))
        components = result.metadata["details"]["electricity_components_kwh_per_kg_dry_input"]
        self.assertEqual(components["headspace_pressurization"], 0)
        self.assertEqual(components["co2_makeup_compression"], 0)

    def test_p3_direct_override_replaces_both_compression_terms(self):
        model = GeneralCarbonationProcess(CarbonationMaterialSettings(0.1),
            CarbonationProcessSettings(
                liquid_to_solid_ratio=0, water_recycle_ratio=0,
                batch_loading_kg_per_m3=300, t_reaction_h=1, t_reaction_C=20,
                initial_cake_moisture=0, final_product_moisture=0,
                pressurization_p2_pa=200000, pressurization_kwh_override=0.02,
                include={"pressurization": True},
            ))
        raw = model.inventory_per_kg_dry_input()
        self.assertEqual(raw["headspace_pressurization_kwh"], 0)
        self.assertEqual(raw["co2_makeup_compression_kwh"], 0)
        self.assertEqual(raw["pressurization_override_kwh"], 0.02)
        self.assertEqual(raw["pressurization_kwh"], 0.02)
        model.process = replace(model.process, pressurization_kwh_override=None,
                                pressurization_p2_pa=101325)
        self.assertEqual(model.pressurization_kwh(), 0)

    def test_factory_use_scales_with_product_mass_and_reaction_time(self):
        for uptake in (0, 0.5):
            process = carbonation_input("general_operating_v2", {"water_mode": "dry"},
                                        uptake=uptake, reaction_time=13)
            response = run_calculation({"functional_unit_kg": 3, "processes": [{
                "process_name": process.process_name, "process_order": process.process_order,
                "parameters": [vars(row) for row in process.parameters],
            }]})
            self.assertTrue(response.ok, response.errors)
            expected = 4.029e-13 * 13
            native = next(row for row in response.records["A"]["exchanges"]
                          if row["flow_key"] == "carbonation_factory_unit")
            final = next(row for row in response.records["C"]["exchanges"]
                         if row["flow_key"] == "carbonation_factory_unit")
            self.assertAlmostEqual(native["process_quantity"] / expected, 1)
            self.assertAlmostEqual(native["native_quantity"] / expected, 1 + uptake)
            self.assertAlmostEqual(final["quantity"] / expected, 3)
            self.assertEqual(native["unit"], "unit")
            self.assertIn("E108-F109", native["source_reference"])

        override = calculate_general_conditions(carbonation_input("general_operating_v2", {
            "water_mode": "dry", "background_overrides": {
                "carbonation_factory_unit_per_kg_product_h": 2e-12},
        }, reaction_time=2))
        self.assertAlmostEqual(override.metadata["inventory"]["carbonation_factory_unit"] / 4e-12, 1)

    def test_reaction_time_must_be_supplied_to_both_entry_points(self):
        process = carbonation_input("general_operating_v2", {"water_mode": "dry"})
        without_time = ProcessInput(process.process_name, process.process_order, [
            row for row in process.parameters if row.parameter_code != "t_reaction_h"
        ])
        with self.assertRaisesRegex(ValueError, "t_reaction_h"):
            calculate_general_conditions(without_time)
        route_inputs = dict(
            liquid_to_solid_ratio=0, water_recycle_ratio=0,
            batch_loading_kg_per_m3=300, t_reaction_C=20,
            initial_cake_moisture=0, final_product_moisture=0,
        )
        with self.assertRaisesRegex(TypeError, "t_reaction_h"):
            CarbonationProcessSettings(**route_inputs)
        for invalid_time in (None, 0, -1, float("nan"), float("inf")):
            with self.subTest(time=invalid_time), self.assertRaisesRegex(ValueError, "t_reaction_h"):
                CarbonationProcessSettings(**route_inputs, t_reaction_h=invalid_time)
        with self.assertRaisesRegex(TypeError, "process"):
            GeneralCarbonationProcess(CarbonationMaterialSettings(0.1))

    def test_resolved_routes_use_the_same_equation_defaults_as_the_website(self):
        for mode in ("dry", "wet"):
            wet = mode == "wet"
            with self.subTest(mode=mode):
                web = calculate_general_conditions(carbonation_input("general_operating_v2", {
                    "water_mode": mode, "water_powder_ratio": 1 if wet else 0,
                    "heat_up": True, "target_temperature_C": 60,
                    "separation": wet, "drying": wet,
                })).metadata["details"]
                model = GeneralCarbonationProcess(CarbonationMaterialSettings(0.1),
                    CarbonationProcessSettings(
                        liquid_to_solid_ratio=1 if wet else 0,
                        water_recycle_ratio=0.8 if wet else 0,
                        batch_loading_kg_per_m3=None if wet else 300,
                        t_reaction_h=1, t_reaction_C=60,
                        initial_cake_moisture=0.12 if wet else 0,
                        final_product_moisture=0.03 if wet else 0,
                        include={"heating": True, "mixing": wet,
                                 "filtration": wet, "drying": wet},
                    ))
                raw = model.inventory_per_kg_dry_input()
                for key in ("heating", "drying"):
                    self.assertAlmostEqual(raw[key + "_kwh"],
                        web["heat_components_kwh_per_kg_dry_input"][key])
                for raw_key, web_key in (("mixing_kwh", "mixing"), ("filtration_kwh", "separation")):
                    self.assertAlmostEqual(raw[raw_key],
                        web["electricity_components_kwh_per_kg_dry_input"][web_key])
                self.assertAlmostEqual(raw["freshwater_makeup_kg"],
                    web["mass_balance_per_kg_dry_input"]["freshwater_makeup_kg"])
                self.assertEqual(model.feed_batch_kg(), web["batch_loading"]["dry_feed_batch_kg"])
                if wet:
                    self.assertEqual(model.active_slurry_volume_m3(), 8)
                else:
                    self.assertEqual(model.feed_batch_kg(), 3000)

    def test_water_defaults_apply_only_to_enabled_separation_and_drying(self):
        for separation, drying in ((False, False), (False, True), (True, False), (True, True)):
            with self.subTest(separation=separation, drying=drying):
                details = calculate_general_conditions(carbonation_input("general_operating_v2", {
                    "water_mode": "wet", "water_powder_ratio": 1,
                    "separation": separation, "drying": drying,
                    "background_overrides": {"water_recycle_ratio": 0.3,
                        "initial_cake_moisture": 0.2, "final_product_moisture": 0.07},
                })).metadata["details"]
                effective = details["effective_model_settings"]
                initial = 0.2 if separation else 1 / 2.1
                final = 0.07 if drying else initial
                self.assertAlmostEqual(effective["initial_cake_moisture"], initial)
                self.assertAlmostEqual(effective["final_product_moisture"], final)
                self.assertEqual(effective["water_recycle_ratio"], 0.3 if separation else 0)
                water = details["mass_balance_per_kg_dry_input"]
                self.assertAlmostEqual(water["final_product_water_kg"], 1.1 * final / (1 - final))
                if not drying:
                    self.assertAlmostEqual(water["evaporated_water_kg"], 0)

    def test_equipment_electricity_and_process_heat_are_separate(self):
        conditions = {
            "water_mode": "wet", "water_powder_ratio": 1,
            "heat_up": True, "target_temperature_C": 60,
            "separation": True, "drying": True,
        }
        current = calculate_general_conditions(carbonation_input("general_operating_v2", conditions))
        new_flows = current.metadata["inventory"]
        self.assertGreater(new_flows["heat_kwh"], 0)
        self.assertGreater(new_flows["electricity_kwh"], 0)
        details = current.metadata["details"]
        self.assertAlmostEqual(
            sum(details["electricity_components_kwh_per_kg_dry_input"].values())
            / details["product_mass_kg_per_kg_dry_input"],
            new_flows["electricity_kwh"],
        )
        self.assertAlmostEqual(
            sum(details["heat_components_kwh_per_kg_dry_input"].values())
            / details["product_mass_kg_per_kg_dry_input"],
            new_flows["heat_kwh"],
        )
        self.assertEqual(current.metadata["model_variant"], "general_operating_v2")

    def test_wet_fill_and_dry_loading_use_separate_route_inputs(self):
        schema = calculation_schema()
        self.assertEqual(schema["ui_default_carbonation_variant"], "general_operating_v2")
        self.assertEqual(schema["input_libraries"]["carbonation_defaults"]["parameters"]["chamber_loading_kg_per_m3"]["default"], 300)
        generic = calculate_general_conditions(carbonation_input(
            "general_operating_v2", {"water_mode": "dry", "gas_mode": "chamber"}))
        self.assertEqual(generic.metadata["details"]["batch_loading"]["dry_feed_batch_kg"], 3000)
        self.assertEqual(generic.metadata["details"]["batch_loading"]["volume_basis"], "total_reactor")
        self.assertNotIn("reactor_fill_fraction", generic.metadata["details"]["background_parameters"])
        self.assertAlmostEqual(generic.metadata["details"]["batch_loading"]["free_gas_volume_m3"],
                               10 - 3000 / 2600)

        semi_dry = calculate_general_conditions(carbonation_input(
            "general_operating_v2", {
                "water_mode": "semi_dry", "water_powder_ratio": 0.1,
                "gas_mode": "chamber",
            }))
        self.assertEqual(semi_dry.metadata["details"]["batch_loading"]["dry_feed_batch_kg"], 3000)
        self.assertAlmostEqual(semi_dry.metadata["details"]["batch_loading"]["free_gas_volume_m3"],
                               10 - 3000 / 2600 - 300 / 1000)

        wet = calculate_general_conditions(carbonation_input(
            "general_operating_v2", {
                "water_mode": "wet", "water_powder_ratio": 1,
            }))
        self.assertEqual(wet.metadata["details"]["batch_loading"]["wet_reactor_fill_fraction"], 0.8)
        self.assertEqual(wet.metadata["details"]["batch_loading"]["active_slurry_volume_m3"], 8)
        self.assertEqual(wet.metadata["details"]["batch_loading"]["free_gas_volume_m3"], 2)
        self.assertNotIn("chamber_loading_kg_per_m3", wet.metadata["details"]["background_parameters"])

        pressurized = calculate_general_conditions(carbonation_input(
            "general_operating_v2", {
                "water_mode": "dry", "pressurize": True,
                "target_pressure_bar": 2,
            }))
        pressure_duty = pressurized.metadata["details"]["electricity_components_kwh_per_kg_dry_input"]["headspace_pressurization"]
        expected = (200000 * (10 - 3000 / 2600) * log(200000 / 101325)
                    / 0.7 / 3_600_000 / 3000)
        self.assertAlmostEqual(pressure_duty, expected)

        with self.assertRaisesRegex(ValueError, "requires nominal reactor volume"):
            calculate_general_conditions(carbonation_input(
                "general_operating_v2", {
                    "water_mode": "dry", "gas_mode": "chamber",
                    "batch_loading_volume_basis": "active_slurry",
                }))
        with self.assertRaisesRegex(ValueError, "wet-route input"):
            calculate_general_conditions(carbonation_input(
                "general_operating_v2", {
                    "water_mode": "dry", "gas_mode": "chamber",
                    "background_overrides": {"reactor_fill_fraction": 0.5},
                }))

        explicit = calculate_general_conditions(carbonation_input(
            "general_operating_v2", {
                "water_mode": "dry", "gas_mode": "chamber",
                "chamber_volume_m3": 10,
                "background_overrides": {
                    "reactor_volume_m3": 10,
                    "chamber_loading_kg_per_m3": 300,
                },
            }))
        self.assertEqual(explicit.metadata["details"]["batch_loading"]["dry_feed_batch_kg"], 3000)
        self.assertEqual(explicit.metadata["details"]["batch_loading"]["volume_basis"], "total_reactor")

    def test_only_current_carbonation_model_is_supported(self):
        schema = calculation_schema()
        self.assertEqual(set(schema["carbonation_variants"]), {"general_operating_v2"})
        self.assertEqual(
            schema["processes"]["Carbonation"]["parameters"]["carbonation_model"]["choices"],
            ("general_operating_v2",),
        )
        with self.assertRaisesRegex(ValueError, "general_operating_v2"):
            calculate_general_conditions(carbonation_input(
                "unsupported_model", {
                    "water_mode": "dry", "gas_mode": "chamber",
                }))

    def test_run_record_includes_process_heat_exchange(self):
        process = carbonation_input("general_operating_v2", {
            "water_mode": "wet", "water_powder_ratio": 1,
            "heat_up": True, "target_temperature_C": 60,
            "separation": True, "drying": True,
        })
        payload = {"processes": [{
            "process_name": process.process_name,
            "process_order": process.process_order,
            "parameters": [{
                "parameter_code": item.parameter_code,
                "parameter_label": item.parameter_label,
                "value": item.value,
                "unit": item.unit,
            } for item in process.parameters],
        }]}
        result = run_calculation(payload)
        self.assertTrue(result.ok, result.errors)
        record = result.to_dict()["records"]
        heat = next(row for row in record["A"]["exchanges"] if row["flow_key"] == "heat_kwh")
        self.assertEqual(heat["role"], "exchange")
        self.assertGreater(heat["process_quantity"], 0)
        self.assertEqual(record["C"]["status"], "unlinked_foreground")


if __name__ == "__main__":
    unittest.main()
