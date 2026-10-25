"""Process-specific calculation plugins."""

from .general_conditions_carbonation import calculate_general_conditions as calculate_carbonation
from .crushing import calculate_crushing
from .grinding import calculate_grinding
from .sorting import calculate_sorting
from .thermal_activation import calculate_thermal_activation
from .sieving import calculate_sieving

__all__ = [
    "calculate_carbonation",
    "calculate_crushing",
    "calculate_grinding",
    "calculate_sieving",
    "calculate_sorting",
    "calculate_thermal_activation",
]
