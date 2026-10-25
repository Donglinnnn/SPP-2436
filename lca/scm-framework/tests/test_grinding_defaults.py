"""Keep direct grinding calculations consistent with the website input contract."""

from math import sqrt
import unittest

from src.calculation.models.grinding import GrindingModel, grinding_library
from src.calculation.modules.grinding import calculate_grinding
from src.calculation.process_settings.grinding import GrindingParams
from src.calculation.schemas import ProcessInput, ProcessParameterRecord
from src.calculation.units import SHORT_TON_TO_TONNE


def grinding_input(**values):
    rows = []
    for code, value in values.items():
        value, unit = value if isinstance(value, tuple) else (value, "")
        rows.append(ProcessParameterRecord(code, code, str(value), unit))
    return ProcessInput("Grinding", 1, rows)


class GrindingDefaultTests(unittest.TestCase):
    def test_work_index_requires_explicit_input_or_selected_material(self):
        with self.assertRaisesRegex(TypeError, "Wi_value"):
            GrindingParams(material_name="custom")
        with self.assertRaisesRegex(TypeError, "Wi_kWh_per_short_ton"):
            GrindingModel.grinding_energy_kwh_per_kg(1000, 200)
        with self.assertRaisesRegex(ValueError, "requires Wi_value"):
            calculate_grinding(grinding_input(F80_um=1000, P80_um=200))
        for value in (None, True, 0, -1, float("nan"), float("inf")):
            with self.subTest(work_index=value), self.assertRaisesRegex(ValueError, "Wi_value"):
                GrindingParams(material_name="custom", Wi_value=value)
        selected = calculate_grinding(grinding_input(
            F80_um=1000, P80_um=200, material_key="dolomite"))
        self.assertGreater(selected.metadata["details"]["unit_electricity_kwh"], 0)

    def test_short_ton_helper_matches_web_with_defaults_and_overrides(self):
        wi_short_ton = 12.0
        for overrides, factors in (({}, 1.15),
                                   ({"material_factor": .8, "auxiliaries_factor": 1.3}, .8 * 1.3)):
            with self.subTest(overrides=overrides):
                direct = GrindingModel.grinding_energy_kwh_per_kg(
                    1000, 200, wi_short_ton, **overrides)
                web = calculate_grinding(grinding_input(
                    F80_um=1000, P80_um=200,
                    Wi_value=(wi_short_ton, "kWh/short ton"), **overrides))
                expected = (10 * wi_short_ton / SHORT_TON_TO_TONNE
                            * (1 / sqrt(200) - 1 / sqrt(1000)) * factors / 1000)
                self.assertAlmostEqual(direct, expected)
                self.assertAlmostEqual(direct, web.metadata["details"]["unit_electricity_kwh"])

    def test_library_calibration_reproduces_anchor_with_shared_defaults(self):
        record = grinding_library()["steel_slag"]
        anchor = record["fine_calibration"]
        target = anchor["target_um"]
        # At the fine-grinding anchor, the calibrated fine stage must reproduce
        # its reported energy before adding the coarse Bond stage and factors.
        expected = (10 * record["Wi_kWh_per_tonne"]
                    * (1 / sqrt(100) - 1 / sqrt(1000))
                    + anchor["energy_kwh_per_tonne"]) * 1.15 / 1000
        direct = GrindingModel.hybrid_grinding_energy_from_material_kwh_per_kg(
            1000, target, "steel_slag", fine_target_um=target,
            fine_anchor_energy_kwh_per_tonne=anchor["energy_kwh_per_tonne"])
        web = calculate_grinding(grinding_input(
            F80_um=1000, P80_um=target, grinding_library_key="steel_slag"))
        self.assertAlmostEqual(direct, expected)
        self.assertAlmostEqual(direct, web.metadata["details"]["unit_electricity_kwh"])

    def test_explicit_fine_grinding_settings_override_defaults(self):
        supplied = dict(transition_um=120, fine_target_um=40,
                        fine_anchor_energy_kwh_per_tonne=18,
                        fine_n=1.5, material_factor=.9, auxiliaries_factor=1.2)
        direct = GrindingModel.hybrid_grinding_energy_from_material_kwh_per_kg(
            1000, 40, "dolomite", **supplied)
        web = calculate_grinding(grinding_input(
            F80_um=1000, P80_um=40, material_key="dolomite", **supplied))
        expected = (10 * 11.27 * (1 / sqrt(120) - 1 / sqrt(1000)) + 18) * .9 * 1.2 / 1000
        self.assertAlmostEqual(direct, expected)
        self.assertAlmostEqual(direct, web.metadata["details"]["unit_electricity_kwh"])


if __name__ == "__main__":
    unittest.main()
