"""Calculation layer for project/process-level computation.

Keep this module pure from Flask/IO concerns.
Input and output types are defined in :mod:`src.calculation.schemas`.
"""

from .engine import run_calculation
from .schemas import CalculationRequest, CalculationResponse

__all__ = ["run_calculation", "CalculationRequest", "CalculationResponse"]
