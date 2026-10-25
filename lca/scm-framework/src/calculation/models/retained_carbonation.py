from __future__ import annotations

from dataclasses import dataclass, field
from math import log, pi
from typing import Any, Dict, Optional

from ..process_settings.carbonation import (
    CARBONATION_ROUTE_PRESETS,
    CarbonationMaterialSettings,
    CarbonationProcessSettings,
    CarbonationRouteSettings,
)
from ..supporting_data.carbonation_reactions import REACTION_HEAT_LIBRARY_KJ_PER_MOL_CO2
from ..supporting_data.co2_supply import (
    CAPTURED_CO2_MINERALIZATION_PLANT_KWH_PER_KG,
    CAPTURED_CO2_SUPPLY_KWH_PER_KG_CO2,
)
from ..supporting_data.physical_constants import (
    MOLAR_GAS_CONSTANT_J_PER_MOL_K, STANDARD_GRAVITY_M_PER_S2,
)
from ..units import KWH_PER_J, KWH_PER_KJ


@dataclass
class GeneralCarbonationProcess:
    material: CarbonationMaterialSettings
    process: CarbonationProcessSettings
    route: CarbonationRouteSettings = field(default_factory=CarbonationRouteSettings)

    @staticmethod
    def get_route_defaults(route: str) -> Dict[str, Any]:
        if route == "lab_benchmark":
            return {
                "liquid_to_solid_ratio": 0.0,
                "gas_circulation": False,
                "pressurization": False,
                "mixing": False,
                "heating": False,
                "clarifier": False,
                "centrifuge": False,
                "filtration": False,
                "drying": False,
                "wastewater": False,
                "comment": "Project-specific laboratory benchmark route.",
            }
        if route not in CARBONATION_ROUTE_PRESETS:
            valid_routes = ["lab_benchmark", *CARBONATION_ROUTE_PRESETS.keys()]
            raise ValueError(
                f"Unknown carbonation_route '{route}'. Available routes: {valid_routes}"
            )
        return dict(CARBONATION_ROUTE_PRESETS[route])

    @staticmethod
    def captured_liquefied_co2_carbonation_kwh(
        co2_uptake_kg: float,
        mineralization_plant_kwh_per_kg_material: float = (
            CAPTURED_CO2_MINERALIZATION_PLANT_KWH_PER_KG
        ),
        co2_supply_kwh_per_kg_co2: float = CAPTURED_CO2_SUPPLY_KWH_PER_KG_CO2,
    ) -> float:
        if co2_uptake_kg < 0:
            raise ValueError("co2_uptake_kg must be non-negative.")
        if mineralization_plant_kwh_per_kg_material < 0:
            raise ValueError("mineralization_plant_kwh_per_kg_material must be non-negative.")
        if co2_supply_kwh_per_kg_co2 < 0:
            raise ValueError("co2_supply_kwh_per_kg_co2 must be non-negative.")
        return (
            mineralization_plant_kwh_per_kg_material
            + co2_supply_kwh_per_kg_co2 * co2_uptake_kg
        )

    def route_defaults(self) -> Dict[str, Any]:
        return self.get_route_defaults(self.route.carbonation_route)

    def include_step(self, key: str) -> bool:
        if key in self.process.include:
            return self.process.include[key]
        return bool(self.route_defaults().get(key, False))

    def include_any_step(self, *keys: str) -> bool:
        if any(key in self.process.include for key in keys):
            return any(self.process.include.get(key, False) for key in keys)
        return any(bool(self.route_defaults().get(key, False)) for key in keys)

    def effective_co2_uptake_kg(self) -> float:
        # Name retained for backward-compatible reports; no realization factor is applied.
        return self.material.co2_uptake_kg

    def product_mass_kg(self) -> float:
        product_mass = 1.0 + self.effective_co2_uptake_kg()
        if product_mass <= 0:
            raise ValueError("Calculated dry carbonated product mass must be positive.")
        return product_mass

    def liquid_to_solid_ratio(self) -> float:
        if self.process.liquid_to_solid_ratio is not None:
            return self.process.liquid_to_solid_ratio
        if self.process.water_kg is not None:
            return self.process.water_kg
        return self.route_defaults()["liquid_to_solid_ratio"]

    def water_charged_kg(self) -> float:
        return self.liquid_to_solid_ratio()

    def water_purge_kg(self) -> float:
        if self.process.water_purge_kg is not None:
            return self.process.water_purge_kg
        if self.process.wastewater_out_kg is not None:
            return self.process.wastewater_out_kg
        return self.water_unrecycled_kg()

    def initial_cake_water_kg(self) -> float:
        """Water retained with the separated solids before drying."""
        if self.process.initial_cake_moisture is not None:
            return self.product_mass_kg() * (
                self.process.initial_cake_moisture
                / (1.0 - self.process.initial_cake_moisture)
            )
        return self.final_product_water_kg() + (
            0.0
            if self.process.evaporated_water_kg is None
            else self.process.evaporated_water_kg
        )

    def final_product_water_kg(self) -> float:
        """Water leaving the system in the product at its specified moisture."""
        if self.process.final_product_moisture is None:
            return 0.0
        return self.product_mass_kg() * (
            self.process.final_product_moisture
            / (1.0 - self.process.final_product_moisture)
        )

    def filtrate_water_kg(self) -> float:
        """Charged water available as filtrate after cake-water retention."""
        filtrate = self.water_charged_kg() - self.initial_cake_water_kg()
        if filtrate < -1.0e-12:
            raise ValueError(
                "Initial cake water exceeds charged process water; check the "
                "liquid-to-solid ratio and cake-moisture specification."
            )
        return max(0.0, filtrate)

    def water_recycled_kg(self) -> float:
        """Recovered filtrate returned to the next steady-state batch."""
        return self.filtrate_water_kg() * self.process.water_recycle_ratio

    def water_unrecycled_kg(self) -> float:
        """Filtrate not returned to the next batch."""
        return self.filtrate_water_kg() - self.water_recycled_kg()

    def freshwater_makeup_kg(self) -> float:
        # At steady state, freshwater replaces wastewater, water leaving with
        # the wet cake (evaporation plus final product moisture), and any
        # separately reported process-water loss.
        return (
            self.wastewater_kg()
            + self.initial_cake_water_kg()
            + self.process.water_loss_kg
        )

    def wastewater_kg(self) -> float:
        if self.process.wastewater_out_kg is not None:
            return self.process.wastewater_out_kg
        return self.water_purge_kg()

    def co2_makeup_kg(self) -> float:
        return self.effective_co2_uptake_kg() / (1.0 - self.process.co2_loss_fraction)

    def co2_lost_kg(self) -> float:
        """Return supplied CO2 that is neither retained nor internally recovered."""
        return self.co2_makeup_kg() - self.effective_co2_uptake_kg()

    def active_slurry_volume_m3(self) -> float:
        """Occupied liquid/solid volume; dry charges use constituent volumes.

        A dry loading density is specified per nominal reactor volume. Its
        interparticle gas space must not be inferred from the wet-slurry fill
        fraction, which applies only when batch mass comes from slurry volume.
        """
        if self.process.active_slurry_volume_m3 is not None:
            return self.process.active_slurry_volume_m3
        if self.process.batch_loading_kg_per_m3 is not None:
            dry_batch_kg = (self.process.reactor_volume_m3
                            * self.process.batch_loading_kg_per_m3)
            return dry_batch_kg * (
                1.0 / self.process.solid_density_kg_per_m3
                + self.liquid_to_solid_ratio() / self.process.water_density_kg_per_m3
            )
        return self.process.reactor_volume_m3 * self.process.reactor_fill_fraction

    def headspace_volume_m3(self) -> float:
        return max(0.0, self.process.reactor_volume_m3 - self.active_slurry_volume_m3())

    def feed_batch_kg(self) -> float:
        if self.process.batch_loading_kg_per_m3 is not None:
            return self.process.reactor_volume_m3 * self.process.batch_loading_kg_per_m3
        denominator = (
            self.liquid_to_solid_ratio() / self.process.water_density_kg_per_m3
            + 1.0 / self.process.solid_density_kg_per_m3
        )
        if denominator <= 0:
            raise ValueError("Batch feed denominator must be positive.")
        return self.active_slurry_volume_m3() / denominator

    def slurry_mass_kg(self) -> float:
        return 1.0 + self.water_charged_kg()

    def mixture_density_kg_per_m3(self) -> float:
        if self.process.mixture_density_kg_per_m3 is not None:
            return self.process.mixture_density_kg_per_m3
        mixture_volume_m3_per_kg_feed = (
            self.water_charged_kg() / self.process.water_density_kg_per_m3
            + 1.0 / self.process.solid_density_kg_per_m3
        )
        if mixture_volume_m3_per_kg_feed <= 0:
            raise ValueError("Mixture volume must be positive.")
        return self.slurry_mass_kg() / mixture_volume_m3_per_kg_feed

    def gas_flow_rate_m3_per_s(self) -> float:
        if self.process.gas_flow_rate_L_per_h is not None:
            return self.process.gas_flow_rate_L_per_h / 1000.0 / 3600.0
        return self.process.gas_flow_rate_m3_per_s

    def gas_liquid_height_m(self) -> float:
        tank_area_m2 = pi * self.process.gas_tank_diameter_m ** 2 / 4.0
        return self.active_slurry_volume_m3() / tank_area_m2

    def gas_slurry_density_kg_per_m3(self) -> float:
        if self.process.gas_slurry_density_kg_per_m3 is not None:
            return self.process.gas_slurry_density_kg_per_m3
        return self.mixture_density_kg_per_m3()

    def gas_pressure_drop_pa(self) -> float:
        if self.process.gas_delta_p_pa is not None:
            return self.process.gas_delta_p_pa
        return (
            self.gas_slurry_density_kg_per_m3()
            * STANDARD_GRAVITY_M_PER_S2
            * self.gas_liquid_height_m()
        )

    def gas_circulation_kwh(self) -> float:
        if not self.include_any_step("co2_delivery", "gas_circulation"):
            return 0.0
        if self.process.gas_circulation_kwh_override is not None:
            return self.process.gas_circulation_kwh_override
        flow_m3_per_s = self.gas_flow_rate_m3_per_s()
        if flow_m3_per_s <= 0:
            if self.process.chamber_control_kwh_per_m3_h <= 0:
                return 0.0
            return (
                self.process.chamber_control_kwh_per_m3_h
                * self.active_slurry_volume_m3()
                * self.process.t_reaction_h
                / self.feed_batch_kg()
            )
        energy_j_batch = (
            flow_m3_per_s
            * self.gas_pressure_drop_pa()
            * self.process.t_reaction_h
            * 3600.0
            / self.process.gas_efficiency
        )
        return energy_j_batch * KWH_PER_J / self.feed_batch_kg()

    def pressurization_components_kwh(self) -> Dict[str, float]:
        """P3 electricity on the internal 1 kg dry-feed basis (SI S1.3 F86–F88).

        Headspace charging is a batch duty. Makeup CO2 is already expressed per
        kg feed, so its isothermal compression term has no batch-mass divisor.
        A direct override replaces total P3; it is not assigned to either term.
        """
        components = {
            "headspace_pressurization_kwh": 0.0,
            "co2_makeup_compression_kwh": 0.0,
            "pressurization_override_kwh": 0.0,
        }
        if not self.include_any_step("compression", "pressurization"):
            return components
        if self.process.pressurization_kwh_override is not None:
            components["pressurization_override_kwh"] = self.process.pressurization_kwh_override
            return components
        p1 = self.process.pressurization_p1_pa
        p2 = self.process.pressurization_p2_pa
        if p2 <= p1:
            return components
        if p1 <= 0:
            raise ValueError("Pressurization inlet pressure must be positive.")
        log_ratio = log(p2 / p1)
        energy_j_batch = (
            p2
            * self.headspace_volume_m3()
            * log_ratio
            / self.process.compressor_efficiency
        )
        components["headspace_pressurization_kwh"] = energy_j_batch * KWH_PER_J / self.feed_batch_kg()
        components["co2_makeup_compression_kwh"] = (
            self.co2_makeup_kg() / self.process.co2_molar_mass_kg_per_mol
            * MOLAR_GAS_CONSTANT_J_PER_MOL_K * self.process.pressurization_temperature_K
            * log_ratio / self.process.compressor_efficiency * KWH_PER_J
        )
        return components

    def pressurization_kwh(self) -> float:
        return sum(self.pressurization_components_kwh().values())

    def carbonation_factory_unit(self) -> float:
        """Factory use per kg dry feed, with the coefficient on product mass."""
        return (self.process.carbonation_factory_unit_per_kg_product_h
                * self.product_mass_kg() * self.process.t_reaction_h)

    def sensible_heating_kj(self) -> float:
        delta_t = max(0.0, self.process.t_reaction_C - self.process.t0_C)
        if delta_t <= 0:
            return 0.0
        return delta_t * (
            self.process.cp_solid_kj_per_kgK
            + self.process.cp_water_kj_per_kgK * self.water_charged_kg()
        )

    def hold_loss_kj(self) -> float:
        delta_t = max(0.0, self.process.t_reaction_C - self.process.t0_C)
        if delta_t <= 0:
            return 0.0
        return (
            self.process.hold_loss_kj_per_kg_h_per_deltaT100K
            * self.slurry_mass_kg()
            * self.process.t_reaction_h
            * delta_t
            / 100.0
        )

    def resolved_reaction_heat_kj_per_mol_co2(self) -> float:
        if self.process.reaction_heat_kj_per_mol_co2 > 0:
            return self.process.reaction_heat_kj_per_mol_co2
        if self.process.reaction_phase is None:
            return 0.0
        return float(
            REACTION_HEAT_LIBRARY_KJ_PER_MOL_CO2[self.process.reaction_phase][
                "reaction_heat_kj_per_mol_co2"
            ]
        )

    def reaction_heat_source(self) -> str:
        if self.process.reaction_heat_kj_per_mol_co2 > 0:
            return "explicit"
        if self.process.reaction_phase is None:
            return "none"
        return self.process.reaction_phase

    def reaction_heat_credit_from_uptake_kj(self) -> float:
        if (
            self.resolved_reaction_heat_kj_per_mol_co2() <= 0
            or self.process.reaction_heat_utilization_factor <= 0
        ):
            return 0.0
        co2_mol = self.effective_co2_uptake_kg() / self.process.co2_molar_mass_kg_per_mol
        return (
            co2_mol
            * self.resolved_reaction_heat_kj_per_mol_co2()
            * self.process.reaction_heat_utilization_factor
        )

    def total_reaction_heat_credit_kj(self) -> float:
        return (
            self.process.reaction_heat_credit_kj
            + self.reaction_heat_credit_from_uptake_kj()
        )

    def net_heating_kj(self) -> float:
        sensible_after_credit = max(
            0.0,
            self.sensible_heating_kj() - self.total_reaction_heat_credit_kj(),
        )
        return sensible_after_credit + self.process.heat_loss_kj + self.hold_loss_kj()

    def heating_kwh(self) -> float:
        if not self.include_step("heating"):
            return 0.0
        if self.process.heating_kwh_override is not None:
            return self.process.heating_kwh_override
        if self.net_heating_kj() <= 0:
            return 0.0
        return self.net_heating_kj() * KWH_PER_KJ / self.process.eta_heating

    def mixing_kwh(self) -> float:
        if not self.include_step("mixing"):
            return 0.0
        if self.process.mixing_kwh_override is not None:
            return self.process.mixing_kwh_override
        if (
            self.process.mixing_power_number is None
            or self.process.impeller_speed_per_s is None
            or self.process.impeller_diameter_m is None
            or self.process.stirring_efficiency is None
        ):
            raise ValueError(
                "mixing requires mixing_power_number (Np), "
                "impeller_speed_per_s (N), impeller_diameter_m (d), "
                "and stirring_efficiency (eta_stir), or an explicit "
                "mixing_kwh_override."
            )
        energy_j_batch = (
            self.process.mixing_power_number
            * self.mixture_density_kg_per_m3()
            * self.process.impeller_speed_per_s ** 3
            * self.process.impeller_diameter_m ** 5
            * self.process.t_reaction_h
            * 3600.0
            / self.process.stirring_efficiency
        )
        return energy_j_batch * KWH_PER_J / self.feed_batch_kg()

    def separation_kwh(self) -> Dict[str, float]:
        slurry_mass = self.slurry_mass_kg()
        clarifier_kwh = (
            self.process.clarifier_kwh_override
            if self.process.clarifier_kwh_override is not None
            else self.process.e_clarifier_kwh_per_kg_slurry * slurry_mass
        )
        centrifuge_kwh = (
            self.process.centrifuge_kwh_override
            if self.process.centrifuge_kwh_override is not None
            else self.process.e_centrifuge_kwh_per_kg_slurry * slurry_mass
        )
        filtration_kwh = (
            self.process.filtration_kwh_override
            if self.process.filtration_kwh_override is not None
            else self.process.e_filtration_kwh_per_kg_dry_feed
        )
        return {
            "clarifier_kwh": clarifier_kwh if self.include_step("clarifier") else 0.0,
            "centrifuge_kwh": centrifuge_kwh if self.include_step("centrifuge") else 0.0,
            "filtration_kwh": filtration_kwh if self.include_step("filtration") else 0.0,
        }

    def evaporated_water_kg(self) -> float:
        if (
            self.process.initial_cake_moisture is not None
            and self.process.final_product_moisture is not None
        ):
            initial_water_per_dry = (
                self.process.initial_cake_moisture
                / (1.0 - self.process.initial_cake_moisture)
            )
            final_water_per_dry = (
                self.process.final_product_moisture
                / (1.0 - self.process.final_product_moisture)
            )
            return self.product_mass_kg() * max(
                0.0,
                initial_water_per_dry - final_water_per_dry,
            )
        return 0.0 if self.process.evaporated_water_kg is None else self.process.evaporated_water_kg

    def drying_kwh(self) -> float:
        if not self.include_step("drying"):
            return 0.0
        if self.process.drying_kwh_override is not None:
            return self.process.drying_kwh_override
        water_evap = self.evaporated_water_kg()
        return (
            water_evap
            * (
                self.process.lambda_vap_kj_per_kg
                + self.process.cp_water_kj_per_kgK * self.process.drying_delta_t_K
            )
            * KWH_PER_KJ
            / self.process.eta_drying
        )

    def water_source_comment(self) -> str:
        if self.process.water_kg is not None:
            return "explicit charged water from case builder"
        if self.process.liquid_to_solid_ratio is not None:
            return "explicit liquid-to-solid ratio"
        return f"{self.route.carbonation_route} route default"

    def inventory_per_kg_dry_input(self) -> Dict[str, float]:
        separation = self.separation_kwh()
        drying_kwh = self.drying_kwh()

        gas_circulation_kwh = self.gas_circulation_kwh()
        pressurization = self.pressurization_components_kwh()
        pressurization_kwh = sum(pressurization.values())
        mixing_kwh = self.mixing_kwh()
        heating_kwh = self.heating_kwh()

        return {
            "dry_input_kg": 1.0,
            "product_mass_kg": self.product_mass_kg(),
            "co2_uptake_original_kg": self.material.co2_uptake_kg,
            "co2_uptake_effective_kg": self.effective_co2_uptake_kg(),
            "co2_makeup_kg": self.co2_makeup_kg(),
            "co2_lost_kg": self.co2_lost_kg(),
            "co2_loss_fraction": self.process.co2_loss_fraction,
            "water_charged_kg": self.water_charged_kg(),
            "initial_cake_water_kg": self.initial_cake_water_kg(),
            "final_product_water_kg": self.final_product_water_kg(),
            "filtrate_water_kg": self.filtrate_water_kg(),
            "water_recycled_kg": self.water_recycled_kg(),
            "water_unrecycled_kg": self.water_unrecycled_kg(),
            "freshwater_makeup_kg": self.freshwater_makeup_kg(),
            "water_input_kg": self.freshwater_makeup_kg(),
            "water_recycle_ratio": self.process.water_recycle_ratio,
            "water_loss_kg": self.process.water_loss_kg,
            "water_purge_kg": self.water_purge_kg(),
            "wastewater_kg": self.wastewater_kg(),
            "water_loop_residual_kg": (
                self.water_charged_kg()
                - self.water_recycled_kg()
                - self.wastewater_kg()
                - self.evaporated_water_kg()
                - self.final_product_water_kg()
            ),
            "external_water_residual_kg": (
                self.freshwater_makeup_kg()
                - self.wastewater_kg()
                - self.evaporated_water_kg()
                - self.final_product_water_kg()
                - self.process.water_loss_kg
            ),
            "liquid_to_solid_ratio": self.liquid_to_solid_ratio(),
            "slurry_mass_kg": self.slurry_mass_kg(),
            "mixture_density_kg_per_m3": self.mixture_density_kg_per_m3(),
            "feed_batch_kg": self.feed_batch_kg(),
            "batch_loading_kg_per_m3": (
                self.process.batch_loading_kg_per_m3 or 0.0
            ),
            "active_slurry_volume_m3": self.active_slurry_volume_m3(),
            "headspace_volume_m3": self.headspace_volume_m3(),
            "gas_liquid_height_m": self.gas_liquid_height_m(),
            "gas_slurry_density_kg_per_m3": self.gas_slurry_density_kg_per_m3(),
            "gas_pressure_drop_pa": self.gas_pressure_drop_pa(),
            "gas_efficiency": self.process.gas_efficiency,
            "chamber_control_kwh_per_m3_h": (
                self.process.chamber_control_kwh_per_m3_h
            ),
            "gas_circulation_kwh": gas_circulation_kwh,
            "gas_handling_kwh": gas_circulation_kwh,
            "pressurization_kwh": pressurization_kwh,
            "compression_kwh": pressurization_kwh,
            **pressurization,
            "carbonation_factory_unit": self.carbonation_factory_unit(),
            "mixing_kwh": mixing_kwh,
            "sensible_heating_kj": self.sensible_heating_kj(),
            "hold_loss_kj": self.hold_loss_kj(),
            "reaction_heat_credit_manual_kj": self.process.reaction_heat_credit_kj,
            "reaction_heat_credit_from_uptake_kj": (
                self.reaction_heat_credit_from_uptake_kj()
            ),
            "reaction_heat_credit_kj": self.total_reaction_heat_credit_kj(),
            "reaction_phase": self.process.reaction_phase or "",
            "reaction_heat_source": self.reaction_heat_source(),
            "reaction_heat_input_kj_per_mol_co2": (
                self.process.reaction_heat_kj_per_mol_co2
            ),
            "reaction_heat_kj_per_mol_co2": (
                self.resolved_reaction_heat_kj_per_mol_co2()
            ),
            "reaction_heat_utilization_factor": (
                self.process.reaction_heat_utilization_factor
            ),
            "co2_molar_mass_kg_per_mol": self.process.co2_molar_mass_kg_per_mol,
            "net_heating_kj": self.net_heating_kj(),
            "heating_kwh": heating_kwh,
            "drying_kwh": drying_kwh,
            "evaporated_water_kg": self.evaporated_water_kg(),
            **separation,
        }

    def inventory_per_kg_product(self) -> Dict[str, float]:
        inv = self.inventory_per_kg_dry_input()
        product_mass = inv["product_mass_kg"]
        normalized = {
            f"{key}_per_kg_product": value / product_mass
            for key, value in inv.items()
            if key != "product_mass_kg"
        }
        normalized["product_mass_kg_per_internal_basis"] = product_mass
        return normalized

    def full_report(self) -> Dict[str, Dict[str, float]]:
        inv = self.inventory_per_kg_dry_input()
        return {
            "route": {
                "carbonation_route": self.route.carbonation_route,
            },
            "mass_balance": {
                "dry_input_kg": inv["dry_input_kg"],
                "co2_uptake_effective_kg": inv["co2_uptake_effective_kg"],
                "product_mass_kg": inv["product_mass_kg"],
            },
            "water": {
                "water_charged_kg": inv["water_charged_kg"],
                "freshwater_makeup_kg": inv["freshwater_makeup_kg"],
                "water_recycle_ratio": inv["water_recycle_ratio"],
                "filtrate_water_kg": inv["filtrate_water_kg"],
                "water_recycled_kg": inv["water_recycled_kg"],
                "initial_cake_water_kg": inv["initial_cake_water_kg"],
                "evaporated_water_kg": inv["evaporated_water_kg"],
                "final_product_water_kg": inv["final_product_water_kg"],
                "water_loss_kg": inv["water_loss_kg"],
                "water_purge_kg": inv["water_purge_kg"],
                "wastewater_kg": inv["wastewater_kg"],
                "water_loop_residual_kg": inv["water_loop_residual_kg"],
                "external_water_residual_kg": inv["external_water_residual_kg"],
            },
            "co2": {
                "co2_makeup_kg": inv["co2_makeup_kg"],
                "co2_uptake_effective_kg": inv["co2_uptake_effective_kg"],
                "co2_loss_fraction": inv["co2_loss_fraction"],
            },
            "unit_operations": {
                "gas_circulation_kwh": inv["gas_circulation_kwh"],
                "pressurization_kwh": inv["pressurization_kwh"],
                "headspace_pressurization_kwh": inv["headspace_pressurization_kwh"],
                "co2_makeup_compression_kwh": inv["co2_makeup_compression_kwh"],
                "pressurization_override_kwh": inv["pressurization_override_kwh"],
                "carbonation_factory_unit": inv["carbonation_factory_unit"],
                "mixing_kwh": inv["mixing_kwh"],
                "sensible_heating_kj": inv["sensible_heating_kj"],
                "hold_loss_kj": inv["hold_loss_kj"],
                "reaction_phase": inv["reaction_phase"],
                "reaction_heat_source": inv["reaction_heat_source"],
                "reaction_heat_kj_per_mol_co2": inv["reaction_heat_kj_per_mol_co2"],
                "reaction_heat_credit_kj": inv["reaction_heat_credit_kj"],
                "net_heating_kj": inv["net_heating_kj"],
                "heating_kwh": inv["heating_kwh"],
                "clarifier_kwh": inv["clarifier_kwh"],
                "centrifuge_kwh": inv["centrifuge_kwh"],
                "filtration_kwh": inv["filtration_kwh"],
                "drying_kwh": inv["drying_kwh"],
            },
            "inventory_per_kg_product": self.inventory_per_kg_product(),
        }
