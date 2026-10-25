from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from ..process_settings.thermal_activation import StandardizedScenario, ThermalActivationSettings


# ============================================================
# Generic thermal activation inventory model
# TGA-driven version
# ============================================================

@dataclass
class FeedComposition:
    """
    Feed masses for one reference recipe.

    All component masses are in kg.
    These masses are used only to define the feed composition and the
    relative input shares of the recipe.


    """

    components_kg: Dict[str, float]

    #     Example:
    #     {"RCP": 1.5} {"MCW": 0.012, "limestone_powder": 0.016, "Na2CO3": 0.0014}

    def total_mass_kg(self) -> float:
        total = sum(self.components_kg.values())
        if total <= 0:
            raise ValueError("Total feed mass must be > 0")
        return total

    def mass_fractions(self) -> Dict[str, float]:
        total = self.total_mass_kg()
        return {name: mass / total for name, mass in self.components_kg.items()}


@dataclass
class TGAIntervalLoss:
    """
    Generic TGA interval.

    Parameters
    ----------
    name
        Interval name.
    start_C, end_C
        Temperature interval.
    loss_fraction
        Fractional mass loss over the full interval, relative to initial dry mass.
        Example: 0.025 means 2.5 wt.% over that interval.
    h2o_share, co2_share
        How the interval loss is partitioned into H2O and CO2.
        Normally h2o_share + co2_share = 1.
    """

    name: str
    start_C: float
    end_C: float
    loss_fraction: float
    h2o_share: float
    co2_share: float

    def __post_init__(self) -> None:
        if self.end_C <= self.start_C:
            raise ValueError(f"Interval '{self.name}' must satisfy end_C > start_C")
        if self.loss_fraction < 0:
            raise ValueError(f"Interval '{self.name}' must have loss_fraction >= 0")
        if self.h2o_share < 0 or self.co2_share < 0:
            raise ValueError(f"Interval '{self.name}' shares must be >= 0")
        share_sum = self.h2o_share + self.co2_share
        if abs(share_sum - 1.0) > 1e-9:
            raise ValueError(f"Interval '{self.name}' must satisfy h2o_share + co2_share = 1")

    def completion_fraction(self, activation_temperature_C: float) -> float:
        """
        For who not enough temperature, the interval is not completed.
        Fraction of this interval assumed completed at the chosen activation temperature.
        Piecewise linear approximation.
        """
        if activation_temperature_C <= self.start_C:
            return 0.0
        if activation_temperature_C >= self.end_C:
            return 1.0
        return (activation_temperature_C - self.start_C) / (self.end_C - self.start_C)

    def included_loss_fraction(self, activation_temperature_C: float) -> float:
        return self.loss_fraction * self.completion_fraction(activation_temperature_C)


@dataclass
class ReactionTerm:
    """
    Optional reaction-enthalpy lower-bound term.

    Parameters
    ----------
    mass_fraction_in_feed
        Reactant mass fraction in the original dry feed.
    enthalpy_kJ_per_kg_reactant
        Reaction enthalpy per kg reactant.
    start_C, end_C
        Optional temperature window for partial completion approximation.
    """

    name: str
    mass_fraction_in_feed: float
    enthalpy_kJ_per_kg_reactant: float
    start_C: float = 0.0
    end_C: float = 0.0

    def completed_fraction(self, activation_temperature_C: float) -> float:
        if self.end_C <= self.start_C:
            return 1.0 if activation_temperature_C > self.start_C else 0.0
        if activation_temperature_C <= self.start_C:
            return 0.0
        if activation_temperature_C >= self.end_C:
            return 1.0
        return (activation_temperature_C - self.start_C) / (self.end_C - self.start_C)


# ============================================================
# General class, fully TGA-driven
# ============================================================

@dataclass
class GeneralThermalActivationProcess:
    feed: FeedComposition
    tga_intervals: List[TGAIntervalLoss]
    settings: ThermalActivationSettings
    scenario: StandardizedScenario = field(default_factory=StandardizedScenario)
    reaction_terms: List[ReactionTerm] = field(default_factory=list)

    def __post_init__(self) -> None:
        _ = self.feed.total_mass_kg()
        if self.settings.activation_temperature_C <= self.settings.ambient_temperature_C:
            raise ValueError("activation_temperature_C must be greater than ambient_temperature_C")
        if self.scenario.gas_exit_temperature_C is None:
            self.scenario.gas_exit_temperature_C = self.settings.activation_temperature_C
        if len(self.tga_intervals) == 0:
            raise ValueError("At least one TGA interval must be provided")
        if self.tga_total_loss_fraction() <= 0:
            raise ValueError("TGA total loss up to the chosen activation temperature must be > 0")
        if self.tga_total_loss_fraction() >= 1.0:
            raise ValueError("TGA total loss fraction must be < 1.0")

    # --------------------------------------------------------
    # 1. Feed recipe
    # --------------------------------------------------------
    def feed_mass_total_kg(self) -> float:
        return self.feed.total_mass_kg()

    def feed_mass_fractions(self) -> Dict[str, float]:
        return self.feed.mass_fractions()

    # --------------------------------------------------------
    # 2. TGA-derived yield and mass loss
    # --------------------------------------------------------
    def included_interval_losses(self) -> List[Dict[str, float]]:
        included = []
        for interval in self.tga_intervals:
            frac = interval.included_loss_fraction(self.settings.activation_temperature_C)
            included.append(
                {
                    "name": interval.name,
                    "included_loss_fraction": frac,
                    "h2o_fraction": frac * interval.h2o_share,
                    "co2_fraction": frac * interval.co2_share,
                }
            )
        return included

    def tga_total_loss_fraction(self) -> float:
        return sum(r["included_loss_fraction"] for r in self.included_interval_losses())

    def tga_solid_yield(self) -> float:
        return 1.0 - self.tga_total_loss_fraction()

    def feed_required_per_kg_product(self) -> float:
        return 1.0 / self.tga_solid_yield()

    def total_mass_loss_per_kg_product(self) -> float:
        return self.feed_required_per_kg_product() - 1.0

    def feed_components_per_kg_product(self) -> Dict[str, float]:
        feed_required = self.feed_required_per_kg_product()
        fractions = self.feed_mass_fractions()
        return {
            name: frac * feed_required
            for name, frac in fractions.items()
        }

    # --------------------------------------------------------
    # 3. TGA-based H2O / CO2 partition
    # --------------------------------------------------------
    def loss_partition(self) -> Dict[str, float]:
        rows = self.included_interval_losses()
        total = sum(r["included_loss_fraction"] for r in rows)
        if total <= 0:
            raise ValueError("Included TGA loss up to activation temperature must be > 0")
        h2o_total = sum(r["h2o_fraction"] for r in rows)
        co2_total = sum(r["co2_fraction"] for r in rows)
        return {
            "total_loss_to_activation_fraction": total,
            "h2o_loss_fraction_of_total": h2o_total / total,
            "co2_loss_fraction_of_total": co2_total / total,
        }

    def emissions_per_kg_product(self) -> Dict[str, float]:
        total_loss = self.total_mass_loss_per_kg_product()
        partition = self.loss_partition()
        h2o = total_loss * partition["h2o_loss_fraction_of_total"]
        co2 = total_loss * partition["co2_loss_fraction_of_total"]
        return {
            "H2O_to_air_kg_per_kg_product": h2o,
            "CO2_to_air_kg_per_kg_product": co2,
        }

    # --------------------------------------------------------
    # 4. Theoretical minimum heat demand
    # --------------------------------------------------------
    def sensible_heat_of_feed(self) -> float:
        delta_t = self.settings.activation_temperature_C - self.settings.ambient_temperature_C
        return (
            self.feed_required_per_kg_product()
            * self.settings.cp_feed_kj_per_kg_k
            * delta_t
        )

    @staticmethod
    def _segment_midpoint(start_C: float, end_C: float) -> float:
        return 0.5 * (start_C + end_C)

    def water_release_heat_breakdown(self) -> Dict[str, float]:
        feed_required = self.feed_required_per_kg_product()
        t0 = self.settings.ambient_temperature_C
        t_boil = 100.0
        t_exit = float(self.scenario.gas_exit_temperature_C)
        free_water_cutoff = self.settings.free_water_evaporation_cutoff_C

        total_q = 0.0
        free_water_total = 0.0
        chemically_released_water_total = 0.0
        details: Dict[str, float] = {}

        for interval in self.tga_intervals:
            included_fraction = interval.included_loss_fraction(self.settings.activation_temperature_C)
            h2o_mass = feed_required * included_fraction * interval.h2o_share
            if h2o_mass <= 0:
                continue

            included_upper_C = min(self.settings.activation_temperature_C, interval.end_C)
            included_span_C = max(included_upper_C - interval.start_C, 0.0)
            if included_span_C <= 0:
                continue

            free_segment_end_C = min(included_upper_C, free_water_cutoff)
            free_segment_span_C = max(free_segment_end_C - interval.start_C, 0.0)
            free_mass = h2o_mass * (free_segment_span_C / included_span_C)
            chemical_mass = max(h2o_mass - free_mass, 0.0)

            q_interval = 0.0
            if free_mass > 0:
                free_water_total += free_mass
                q_free = (
                    free_mass * self.settings.cp_liquid_water_kj_per_kg_k * max(t_boil - t0, 0.0)
                    + free_mass * self.settings.latent_heat_h2o_kj_per_kg
                    + free_mass * self.settings.cp_h2o_steam_kj_per_kg_k * max(t_exit - t_boil, 0.0)
                )
                q_interval += q_free
                details[f"H2O_free_water_{interval.name}_kg_per_kg_product"] = free_mass
                details[f"Q_H2O_free_water_{interval.name}_kJ_per_kg_product"] = q_free

            if chemical_mass > 0:
                chemically_released_water_total += chemical_mass
                chemical_segment_start_C = max(interval.start_C, free_water_cutoff)
                release_temperature_C = self._segment_midpoint(
                    chemical_segment_start_C,
                    included_upper_C,
                )
                q_chemical = (
                    chemical_mass
                    * self.settings.cp_h2o_steam_kj_per_kg_k
                    * max(t_exit - release_temperature_C, 0.0)
                )
                q_interval += q_chemical
                details[f"H2O_chemical_{interval.name}_kg_per_kg_product"] = chemical_mass
                details[f"H2O_chemical_release_temperature_{interval.name}_C"] = release_temperature_C
                details[f"Q_H2O_chemical_{interval.name}_kJ_per_kg_product"] = q_chemical

            total_q += q_interval
            details[f"Q_H2O_total_{interval.name}_kJ_per_kg_product"] = q_interval

        details["H2O_free_water_total_kg_per_kg_product"] = free_water_total
        details["H2O_chemical_total_kg_per_kg_product"] = chemically_released_water_total
        details["Q_water_release_kJ_per_kg_product"] = total_q
        return details

    def water_release_heat(self) -> float:
        return self.water_release_heat_breakdown()["Q_water_release_kJ_per_kg_product"]

    def co2_offgas_heat(self) -> float:
        emissions = self.emissions_per_kg_product()
        co2 = emissions["CO2_to_air_kg_per_kg_product"]
        delta_t = float(self.scenario.gas_exit_temperature_C) - self.settings.ambient_temperature_C
        return co2 * self.settings.cp_co2_kj_per_kg_k * max(delta_t, 0.0)

    def reaction_heat_lower_bound(self) -> Dict[str, float]:
        feed_required = self.feed_required_per_kg_product()
        total_q = 0.0
        details: Dict[str, float] = {}

        for term in self.reaction_terms:
            reactant_mass = feed_required * term.mass_fraction_in_feed * term.completed_fraction(
                self.settings.activation_temperature_C
            )
            q = reactant_mass * term.enthalpy_kJ_per_kg_reactant
            details[f"reactant_mass_{term.name}_kg_per_kg_product"] = reactant_mass
            details[f"Q_{term.name}_kJ_per_kg_product"] = q
            total_q += q

        details["Q_reaction_total_kJ_per_kg_product"] = total_q
        return details

    def theoretical_minimum_heat(self) -> Dict[str, float]:
        q_solid = self.sensible_heat_of_feed()
        q_water_details = self.water_release_heat_breakdown()
        q_water = q_water_details["Q_water_release_kJ_per_kg_product"]
        q_co2 = self.co2_offgas_heat()
        q_rxn = self.reaction_heat_lower_bound()["Q_reaction_total_kJ_per_kg_product"]
        q_min = q_solid + q_water + q_co2 + q_rxn
        return {
            "Q_solid_heating_kJ_per_kg_product": q_solid,
            **q_water_details,
            "Q_water_release_kJ_per_kg_product": q_water,
            "Q_CO2_offgas_kJ_per_kg_product": q_co2,
            "Q_reaction_total_kJ_per_kg_product": q_rxn,
            "Q_min_kJ_per_kg_product": q_min,
        }

    # --------------------------------------------------------
    # 5. Standardized practical heat demand
    # --------------------------------------------------------
    def hold_loss(self) -> float:
        delta_t = self.settings.activation_temperature_C - self.settings.ambient_temperature_C
        normalized_delta_t = delta_t / 100.0
        return (
            self.scenario.hold_loss_kj_per_kg_h_per_deltaT100K
            * self.settings.holding_time_h
            * normalized_delta_t
        )

    def standardized_practical_heat(self) -> Dict[str, float]:
        q_min = self.theoretical_minimum_heat()["Q_min_kJ_per_kg_product"]
        q_heatup_adjusted = self.scenario.lambda_heatup * q_min
        q_hold = self.hold_loss()
        q_std = q_heatup_adjusted + q_hold
        return {
            "Q_heatup_adjusted_kJ_per_kg_product": q_heatup_adjusted,
            "Q_hold_loss_kJ_per_kg_product": q_hold,
            "Q_std_kJ_per_kg_product": q_std,
            "Q_std_kWh_per_kg_product": q_std / 3600.0,
        }

    # --------------------------------------------------------
    # 6. Final inventory
    # --------------------------------------------------------
    def inventory_per_kg_product(self) -> Dict[str, float]:
        inv: Dict[str, float] = {}
        inv.update(self.feed_components_per_kg_product())
        inv.update(self.emissions_per_kg_product())
        q_min = self.theoretical_minimum_heat()
        q_std = self.standardized_practical_heat()
        inv["activated_product_kg_per_kg_product"] = 1.0
        inv["standardized_heat_kJ_per_kg_product"] = q_std["Q_std_kJ_per_kg_product"]
        inv["standardized_heat_kWh_per_kg_product"] = q_std["Q_std_kWh_per_kg_product"]
        inv["tga_total_loss_fraction"] = self.tga_total_loss_fraction()
        inv["tga_solid_yield"] = self.tga_solid_yield()
        inv["total_mass_loss_kg_per_kg_product"] = self.total_mass_loss_per_kg_product()
        inv["Q_min_kJ_per_kg_product"] = q_min["Q_min_kJ_per_kg_product"]
        inv["activation_temperature_C"] = self.settings.activation_temperature_C
        inv["scenario_name"] = self.scenario.name
        return inv

    def full_report(self) -> Dict[str, Dict[str, float]]:
        return {
            "feed_recipe": {
                "feed_mass_total_kg": self.feed_mass_total_kg(),
                **{f"feed_fraction_{k}": v for k, v in self.feed_mass_fractions().items()},
            },
            "tga_yield": {
                "tga_total_loss_fraction": self.tga_total_loss_fraction(),
                "tga_solid_yield": self.tga_solid_yield(),
                "feed_required_per_kg_product": self.feed_required_per_kg_product(),
                "total_mass_loss_per_kg_product": self.total_mass_loss_per_kg_product(),
            },
            "loss_partition": self.loss_partition(),
            "emissions": self.emissions_per_kg_product(),
            "reaction_heat_lower_bound": self.reaction_heat_lower_bound(),
            "theoretical_minimum_heat": self.theoretical_minimum_heat(),
            "standardized_practical_heat": self.standardized_practical_heat(),
            "inventory": self.inventory_per_kg_product(),
        }
