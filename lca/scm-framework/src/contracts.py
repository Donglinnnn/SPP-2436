SUPPORTED_PRODUCT_TYPES = {"SCM"}

API_PREFIX_V1 = "/api/v1"

DEFAULT_PRODUCT_TYPE = "SCM"
DEFAULT_MATERIAL_TYPE = "Waste"
DEFAULT_REFERENCE_PRODUCT = "SCM product"
DEFAULT_SYSTEM_BOUNDARY = "A1-A3"


def parameter_value_text(value):
    """Stable text storage shared by JSON requests and SQLite; preserve 0/False."""
    import json

    if value is None:
        return ""
    if isinstance(value, (dict, list, bool)):
        return json.dumps(value, ensure_ascii=False, allow_nan=False)
    return str(value)
