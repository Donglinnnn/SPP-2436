"""Public thermal-reaction schema and heat accounting survive module reorganizations."""

import json
import unittest
from dataclasses import replace

from src.calculation.modules.thermal_activation import calculate_thermal_activation
from src.calculation.parameters import calculation_schema
from src.calculation.process_settings.thermal_activation import ThermalActivationSettings
from src.calculation.schemas import ProcessInput, ProcessParameterRecord
from src.calculation.supporting_data.infrastructure import THERMAL_FACTORY_UNIT_PER_KG_PRODUCT_H


def thermal_input(interval, *, reaction_terms=None, activation_temperature_C=550, holding_time_h=1):
    values = {
        "activation_temperature_C": (str(activation_temperature_C), "deg C"),
        "holding_time_h": (str(holding_time_h), "h"),
        "tga_intervals_table": (json.dumps([interval]), ""),
    }
    if reaction_terms is not None:
        values["reaction_terms"] = (json.dumps(reaction_terms), "")
    return ProcessInput(
        "Thermal activation", 1,
        [ProcessParameterRecord(code, code, value, unit)
         for code, (value, unit) in values.items()],
    )


class ThermalReactionContractTests(unittest.TestCase):
    def test_total_intervals_is_the_only_basis_and_rejects_overlapping_gas_losses(self):
        interval = {"name": "water_loss", "start_C": 400, "end_C": 550,
                    "loss_fraction": 0.01, "h2o_share": 1, "co2_share": 0}
        original = thermal_input(interval)
        baseline = calculate_thermal_activation(original)
        for basis in ("", "total_intervals"):
            with self.subTest(basis=basis):
                supplied = replace(original, parameters=[*original.parameters,
                    ProcessParameterRecord("tga_basis", "TGA basis", basis, "")])
                result = calculate_thermal_activation(supplied)
                self.assertEqual(result.metadata["inventory"], baseline.metadata["inventory"])
                self.assertEqual(result.metadata["details"], baseline.metadata["details"])
        schema = calculation_schema()
        self.assertEqual(schema["thermal_tga_basis"], ["total_intervals"])
        self.assertEqual(schema["processes"]["Thermal activation"]["parameters"]
                         ["tga_basis"]["choices"], ("total_intervals",))

        gas_channels = replace(original, parameters=[*original.parameters,
            ProcessParameterRecord("tga_basis", "TGA basis", "gas_channels", "")])
        with self.assertRaisesRegex(ValueError, "gas_channels.*no longer supported"):
            calculate_thermal_activation(gas_channels)

        overlapping = {"name": "co2_loss", "start_C": 500, "end_C": 650,
                       "loss_fraction": 0.01, "h2o_share": 0, "co2_share": 1}
        overlapping_input = replace(original, parameters=[
            replace(parameter, value=json.dumps([interval, overlapping]))
            if parameter.parameter_code == "tga_intervals_table" else parameter
            for parameter in original.parameters
        ])
        with self.assertRaisesRegex(ValueError, "TGA intervals must not overlap"):
            calculate_thermal_activation(overlapping_input)

    def test_holding_time_is_required_and_invalid_values_are_rejected(self):
        interval = {"name": "isolated_portlandite", "reaction_key": "portlandite_dehydroxylation_v1",
                    "loss_fraction": 0.01}
        with self.assertRaisesRegex(TypeError, "holding_time_h"):
            ThermalActivationSettings(550)
        # An old positional time must not become a heat-capacity override.
        with self.assertRaises(TypeError):
            ThermalActivationSettings(550, 25, 1)
        missing = thermal_input(interval)
        missing = replace(missing, parameters=[parameter for parameter in missing.parameters
                                              if parameter.parameter_code != "holding_time_h"])
        with self.assertRaisesRegex(ValueError, "Required parameter is missing: holding_time_h"):
            calculate_thermal_activation(missing)
        defaults = calculation_schema()["input_libraries"]["thermal_defaults"]["settings"]
        self.assertNotIn("holding_time_h", defaults)

        for value in (None, True, -1, float("nan"), float("inf"), "1"):
            with self.subTest(raw=value):
                with self.assertRaisesRegex(ValueError, "holding_time_h"):
                    ThermalActivationSettings(550, holding_time_h=value)
        for value in (None, True, -1, float("nan"), float("inf")):
            with self.subTest(web=value):
                with self.assertRaisesRegex(ValueError, "holding_time_h"):
                    calculate_thermal_activation(thermal_input(interval, holding_time_h=value))

    def test_zero_holding_time_removes_holding_heat_and_factory_use(self):
        interval = {"name": "isolated_portlandite", "reaction_key": "portlandite_dehydroxylation_v1",
                    "loss_fraction": 0.01}
        self.assertEqual(ThermalActivationSettings(550, holding_time_h=0).holding_time_h, 0)
        zero = calculate_thermal_activation(thermal_input(interval, holding_time_h=0))
        one = calculate_thermal_activation(thermal_input(interval, holding_time_h=1))
        zero_inventory = dict(zero.metadata["inventory"])
        one_inventory = dict(one.metadata["inventory"])
        self.assertAlmostEqual(one_inventory.pop("heat_kwh") - zero_inventory.pop("heat_kwh"),
                               22 * (550 - 25) / 100 / 3600)
        self.assertEqual(zero_inventory.pop("thermal_factory_unit"), 0)
        self.assertEqual(one_inventory.pop("thermal_factory_unit"), THERMAL_FACTORY_UNIT_PER_KG_PRODUCT_H)
        self.assertEqual(zero_inventory, one_inventory)

    def test_schema_exposes_independent_catalog_with_reference_and_descriptive_rows(self):
        catalog = calculation_schema()["input_libraries"]["thermal_reactions"]
        self.assertEqual(len(catalog), 8)
        portlandite = catalog["portlandite_dehydroxylation_v1"]
        self.assertEqual(portlandite["kind"], "chemical_reaction")
        self.assertEqual((portlandite["h2o_share"], portlandite["co2_share"]), (1, 0))
        self.assertEqual(portlandite["reference_enthalpy_kj_per_kg_reactant"], 1486)
        self.assertEqual((portlandite["start_C"], portlandite["end_C"]), (400, 550))
        descriptive = catalog["bound_water_release_v1"]
        self.assertEqual(descriptive["kind"], "process_description")
        self.assertNotIn("reference_enthalpy_kj_per_kg_reactant", descriptive)

        catalog["portlandite_dehydroxylation_v1"]["start_C"] = -1
        self.assertEqual(
            calculation_schema()["input_libraries"]["thermal_reactions"]
            ["portlandite_dehydroxylation_v1"]["start_C"], 400,
        )

    def test_pure_reaction_adds_stoichiometric_heat_once_to_process_heat(self):
        selected = {"name": "isolated_portlandite", "reaction_key": "portlandite_dehydroxylation_v1",
                    "loss_fraction": 0.01}
        manual = {"name": "isolated_portlandite", "start_C": 400, "end_C": 550,
                  "loss_fraction": 0.01, "h2o_share": 1, "co2_share": 0}
        with_reference = calculate_thermal_activation(thermal_input(selected))
        without_reference = calculate_thermal_activation(thermal_input(manual))
        details = with_reference.metadata["details"]
        baseline = without_reference.metadata["details"]
        reaction_mass = 0.01 / 0.99 * 74.0927 / 18.0153
        reaction_heat = reaction_mass * 1486

        self.assertEqual(details["reaction_heat_basis"], "tga_reference")
        self.assertEqual(baseline["reaction_heat_basis"], "excluded")
        self.assertEqual(len(details["effective_reaction_terms"]), 1)
        self.assertAlmostEqual(details["reaction_heat_lower_bound"]
                               ["Q_reaction_total_kJ_per_kg_product"], reaction_heat)
        self.assertAlmostEqual(baseline["reaction_heat_lower_bound"]
                               ["Q_reaction_total_kJ_per_kg_product"], 0)
        self.assertAlmostEqual(
            with_reference.metadata["inventory"]["heat_kwh"]
            - without_reference.metadata["inventory"]["heat_kwh"],
            1.15 * reaction_heat / 3600,
        )
        self.assertEqual(with_reference.metadata["inventory"]["electricity_kwh"], 0)
        self.assertAlmostEqual(with_reference.metadata["inventory"]["upstream_input_kg"], 1 / 0.99)
        self.assertAlmostEqual(with_reference.metadata["inventory"]["water_to_air_kg"], 0.01 / 0.99)

    def test_descriptive_row_excludes_reference_heat_and_explicit_term_takes_precedence(self):
        descriptive = {"name": "bound_water", "reaction_key": "bound_water_release_v1",
                       "loss_fraction": 0.01}
        result = calculate_thermal_activation(thermal_input(descriptive))
        self.assertEqual(result.metadata["details"]["reaction_heat_basis"], "excluded")
        self.assertEqual(result.metadata["details"]["selected_tga_reactions"][0]
                         ["include_reaction_heat"], False)
        self.assertEqual(result.metadata["details"]["reaction_heat_lower_bound"]
                         ["Q_reaction_total_kJ_per_kg_product"], 0)

        selected = {"name": "isolated_portlandite", "reaction_key": "portlandite_dehydroxylation_v1",
                    "loss_fraction": 0.01}
        explicit = [{"name": "measured_term", "mass_fraction_in_feed": 0.02,
                     "enthalpy_kJ_per_kg_reactant": 1000}]
        result = calculate_thermal_activation(thermal_input(selected, reaction_terms=explicit))
        details = result.metadata["details"]
        self.assertEqual(details["reaction_heat_basis"], "explicit")
        self.assertEqual([term["name"] for term in details["effective_reaction_terms"]], ["measured_term"])
        self.assertAlmostEqual(details["reaction_heat_lower_bound"]
                               ["Q_reaction_total_kJ_per_kg_product"], 0.02 / 0.99 * 1000)

    def test_obsolete_heat_switch_is_rejected_instead_of_silently_changing_heat(self):
        for reaction_key in (None, "portlandite_dehydroxylation_v1"):
            for supplied in (False, True, None):
                interval = {"name": "isolated_portlandite", "loss_fraction": 0.01,
                            "start_C": 400, "end_C": 550, "h2o_share": 1, "co2_share": 0,
                            "include_reaction_heat": supplied}
                if reaction_key:
                    interval["reaction_key"] = reaction_key
                with self.subTest(reaction_key=reaction_key, supplied=supplied):
                    with self.assertRaisesRegex(ValueError, "include_reaction_heat is not a supported input"):
                        calculate_thermal_activation(thermal_input(interval))


if __name__ == "__main__":
    unittest.main()
