"""Validation helpers shared by carbonation operating-condition adapters."""
from math import isfinite


def numeric(config, key, *, default=None, minimum=0, positive=False):
    value = config.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError(f"{key}: enter a finite number")
    if value < minimum or (positive and value == minimum):
        raise ValueError(f"{key}: must be {'greater than' if positive else 'at least'} {minimum}")
    return value


def switch(config, key, default=False):
    value = config.get(key, default)
    if not isinstance(value, bool):
        raise ValueError(f"{key}: expected a checkbox boolean")
    return value
