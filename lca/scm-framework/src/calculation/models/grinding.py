"""Generic Bond and hybrid grinding equations; no database imports or writes."""
from copy import deepcopy
from typing import Dict, Any, Optional
from math import log, sqrt
from ..process_settings.grinding import GrindingParams
from ..process_settings.grinding_defaults import DEFAULTS, REFERENCE_PRODUCT, WORK_INDEX_UNIT
from ..supporting_data.grinding_materials import FINE_ANCHORS, MATERIAL_WIFI_LIBRARY
from ..supporting_data.version import LIBRARY_VERSION
from ..units import SHORT_TON_TO_TONNE


class GrindingModel:
    MATERIAL_WIFI_LIBRARY = MATERIAL_WIFI_LIBRARY

    @staticmethod
    def get_default_wi_from_material(material_key: str) -> float:
        if material_key not in MATERIAL_WIFI_LIBRARY:
            raise KeyError(
                f"Unknown material_key '{material_key}'. "
                f"Available keys: {list(MATERIAL_WIFI_LIBRARY.keys())}"
            )
        return MATERIAL_WIFI_LIBRARY[material_key]["Wi_kWh_per_tonne"]

    @staticmethod
    def get_material_metadata(material_key: str) -> Dict[str, Any]:
        if material_key not in MATERIAL_WIFI_LIBRARY:
            raise KeyError(
                f"Unknown material_key '{material_key}'. "
                f"Available keys: {list(MATERIAL_WIFI_LIBRARY.keys())}"
            )
        return MATERIAL_WIFI_LIBRARY[material_key]

    @staticmethod
    def make_params_from_material(
        material_key: str,
        transition_um: float = DEFAULTS["transition_um"],
        fine_target_um: Optional[float] = None,
        fine_anchor_energy_kwh_per_tonne: Optional[float] = None,
        fine_n: Optional[float] = DEFAULTS["fine_n"],
        material_factor: float = DEFAULTS["material_factor"],
        auxiliaries_factor: float = DEFAULTS["auxiliaries_factor"],
        reference_product: str = REFERENCE_PRODUCT,
        comment: str = "",
    ) -> GrindingParams:
        rec = GrindingModel.get_material_metadata(material_key)
        fine_K = None
        if fine_target_um is not None and fine_anchor_energy_kwh_per_tonne is not None:
            fine_K = GrindingModel.calibrate_fine_K_from_anchor(
                x_in_um=transition_um,
                x_out_um=fine_target_um,
                E_anchor_kwh_per_tonne=fine_anchor_energy_kwh_per_tonne,
                n_fine=fine_n,
            )
        return GrindingParams(
            material_name=material_key,
            Wi_value=rec["Wi_kWh_per_tonne"],
            Wi_unit=WORK_INDEX_UNIT,
            transition_um=transition_um,
            fine_K=fine_K,
            fine_n=fine_n if fine_K is not None else None,
            material_factor=material_factor,
            auxiliaries_factor=auxiliaries_factor,
            reference_product=reference_product,
            comment=comment,
        )

    @staticmethod
    def _validate_sizes(F80_um: float, P80_um: float) -> None:
        if F80_um <= 0 or P80_um <= 0:
            raise ValueError("F80_um and P80_um must be positive")
        if P80_um >= F80_um:
            raise ValueError("P80_um must be smaller than F80_um for size reduction")

    @staticmethod
    def bond_specific_energy_kwh_per_tonne(
        F80_um: float,
        P80_um: float,
        Wi_kWh_per_tonne: float,
    ) -> float:
        GrindingModel._validate_sizes(F80_um, P80_um)
        return 10.0 * Wi_kWh_per_tonne * (1.0 / sqrt(P80_um) - 1.0 / sqrt(F80_um))

    @staticmethod
    def bond_specific_energy_from_material_kwh_per_tonne(
        F80_um: float,
        P80_um: float,
        material_key: str,
        material_factor: float = DEFAULTS["material_factor"],
        auxiliaries_factor: float = DEFAULTS["auxiliaries_factor"],
    ) -> float:
        Wi = GrindingModel.get_default_wi_from_material(material_key)
        energy = GrindingModel.bond_specific_energy_kwh_per_tonne(
            F80_um=F80_um,
            P80_um=P80_um,
            Wi_kWh_per_tonne=Wi,
        )
        return energy * material_factor * auxiliaries_factor

    @staticmethod
    def bond_specific_energy_from_material_kwh_per_kg(
        F80_um: float,
        P80_um: float,
        material_key: str,
        material_factor: float = DEFAULTS["material_factor"],
        auxiliaries_factor: float = DEFAULTS["auxiliaries_factor"],
    ) -> float:
        return GrindingModel.bond_specific_energy_from_material_kwh_per_tonne(
            F80_um=F80_um,
            P80_um=P80_um,
            material_key=material_key,
            material_factor=material_factor,
            auxiliaries_factor=auxiliaries_factor,
        ) / 1000.0

    @staticmethod
    def calibrate_fine_K_from_anchor(
        x_in_um: float,
        x_out_um: float,
        E_anchor_kwh_per_tonne: float,
        n_fine: float,
    ) -> float:
        if x_in_um <= 0 or x_out_um <= 0:
            raise ValueError("x_in_um and x_out_um must be positive")
        if x_out_um >= x_in_um:
            raise ValueError("x_out_um must be smaller than x_in_um")
        if E_anchor_kwh_per_tonne <= 0:
            raise ValueError("E_anchor_kwh_per_tonne must be positive")
        if abs(n_fine - 1.0) < 1e-12:
            return E_anchor_kwh_per_tonne / log(x_in_um / x_out_um)
        denom = x_out_um ** (1.0 - n_fine) - x_in_um ** (1.0 - n_fine)
        return E_anchor_kwh_per_tonne * (n_fine - 1.0) / denom

    @staticmethod
    def charles_hukki_specific_energy_kwh_per_tonne(
        x_in_um: float,
        x_out_um: float,
        K: float,
        n: float,
    ) -> float:
        if x_in_um <= 0 or x_out_um <= 0:
            raise ValueError("x_in_um and x_out_um must be positive")
        if x_out_um >= x_in_um:
            raise ValueError("x_out_um must be smaller than x_in_um")
        if K <= 0:
            raise ValueError("K must be positive")
        if abs(n - 1.0) < 1e-12:
            return K * log(x_in_um / x_out_um)
        return K / (n - 1.0) * (x_out_um ** (1.0 - n) - x_in_um ** (1.0 - n))

    @staticmethod
    def hybrid_grinding_energy_kwh_per_tonne(
        F80_um: float,
        P80_um: float,
        params: GrindingParams,
    ) -> float:
        GrindingModel._validate_sizes(F80_um, P80_um)
        x_tr = params.transition_um
        if x_tr <= 0:
            raise ValueError("transition_um must be positive")

        Wi_tonne = params.Wi_kWh_per_tonne()
        energy = 0.0

        if F80_um > x_tr:
            bond_target_um = max(P80_um, x_tr)
            energy += GrindingModel.bond_specific_energy_kwh_per_tonne(
                F80_um=F80_um,
                P80_um=bond_target_um,
                Wi_kWh_per_tonne=Wi_tonne,
            )

        if P80_um < x_tr:
            if params.fine_K is None or params.fine_n is None:
                raise ValueError(
                    "fine_K and fine_n are required when P80_um < transition_um"
                )
            fine_x_in_um = x_tr if F80_um > x_tr else F80_um
            energy += GrindingModel.charles_hukki_specific_energy_kwh_per_tonne(
                x_in_um=fine_x_in_um,
                x_out_um=P80_um,
                K=params.fine_K,
                n=params.fine_n,
            )

        energy *= params.material_factor
        energy *= params.auxiliaries_factor
        return energy

    @staticmethod
    def hybrid_grinding_energy_from_material_kwh_per_kg(
        F80_um: float,
        P80_um: float,
        material_key: str,
        transition_um: float = DEFAULTS["transition_um"],
        fine_target_um: Optional[float] = None,
        fine_anchor_energy_kwh_per_tonne: Optional[float] = None,
        fine_n: Optional[float] = DEFAULTS["fine_n"],
        material_factor: float = DEFAULTS["material_factor"],
        auxiliaries_factor: float = DEFAULTS["auxiliaries_factor"],
    ) -> float:
        params = GrindingModel.make_params_from_material(
            material_key=material_key,
            transition_um=transition_um,
            fine_target_um=fine_target_um,
            fine_anchor_energy_kwh_per_tonne=fine_anchor_energy_kwh_per_tonne,
            fine_n=fine_n,
            material_factor=material_factor,
            auxiliaries_factor=auxiliaries_factor,
        )
        return GrindingModel.hybrid_grinding_energy_kwh_per_tonne(
            F80_um=F80_um,
            P80_um=P80_um,
            params=params,
        ) / 1000.0

    @staticmethod
    def bond_specific_energy_kwh_per_kg(
        F80_um: float,
        P80_um: float,
        Wi_kWh_per_short_ton: float,
    ) -> float:
        return GrindingModel.bond_specific_energy_kwh_per_tonne(
            F80_um=F80_um,
            P80_um=P80_um,
            Wi_kWh_per_tonne=Wi_kWh_per_short_ton / SHORT_TON_TO_TONNE,
        ) / 1000.0

    @staticmethod
    def grinding_energy_kwh_per_kg(
        F80_um: float,
        P80_um: float,
        Wi_kWh_per_short_ton: float,
        material_factor: float = DEFAULTS["material_factor"],
        auxiliaries_factor: float = DEFAULTS["auxiliaries_factor"],
    ) -> float:
        """Hybrid helper with an explicit work index in kWh per US short ton.

        Other defaults match the website. For fine grinding below the default
        transition, use GrindingParams with an explicit fine calibration.
        """
        params = GrindingParams(
            material_name="custom",
            Wi_value=Wi_kWh_per_short_ton,
            Wi_unit="kWh_per_short_ton",
            material_factor=material_factor,
            auxiliaries_factor=auxiliaries_factor,
        )
        return GrindingModel.hybrid_grinding_energy_kwh_per_tonne(
            F80_um=F80_um,
            P80_um=P80_um,
            params=params,
        ) / 1000.0


def grinding_library():
    """Resolve reference records and calculate fine-grinding calibration values."""
    records = {}
    for key, wi in MATERIAL_WIFI_LIBRARY.items():
        anchor = deepcopy(FINE_ANCHORS.get(key))
        fine_k = (GrindingModel.calibrate_fine_K_from_anchor(
            DEFAULTS["transition_um"], anchor["target_um"],
            anchor["energy_kwh_per_tonne"], DEFAULTS["fine_n"]
        ) if anchor else None)
        records[key] = {
            **deepcopy(wi), "label": key.replace("_", " ").capitalize(),
            "fine_K": fine_k, "fine_K_unit": "kWh·µm/t", "fine_n": DEFAULTS["fine_n"],
            "transition_um": DEFAULTS["transition_um"], "fine_calibration": anchor,
            "source_file": "../Cycle2/GrindingModel.py", "version": LIBRARY_VERSION,
        }
    return records
