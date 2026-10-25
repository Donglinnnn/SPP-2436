"""Crushing input contract; its unit inventory is in supporting_data."""

from ..parameters import text_spec
from .recovery import recovery_specs


CRUSHING_SPECS = {
    "inventory_id": text_spec(default="user-crushing-2026-09-22", choices=("cycle2-crushing-v1", "user-crushing-2026-09-22")),
    **recovery_specs(with_yield=True),
}
