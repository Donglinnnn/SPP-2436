"""Article CO2-supply inventories, per kilogram of external make-up CO2.

These are foreground recipes supplied by the author. Activity names and
locations must resolve exactly in the configured local background database.
"""

SOURCES = {
    "C0": {
        "label": "C0 · Cement-kiln flue-gas capture and conditioning",
        "entries": [
            ("market group for electricity, low voltage", "RER", 0.0315, "kilowatt hour"),
            ("market group for electricity, low voltage", "RER", 0.0206, "kilowatt hour"),
            ("market group for electricity, low voltage", "RER", 0.0963, "kilowatt hour"),
            ("market for heat, district or industrial, natural gas", "Europe without Switzerland", 3.65, "megajoule"),
            ("market for monoethanolamine", "GLO", 0.00140, "kilogram"),
            ("market for sodium hydroxide, without water, in 50% solution state", "RER", 0.000536, "kilogram"),
            ("market group for tap water", "GLO", 0.473, "kilogram"),
            ("treatment of spent solvent mixture, hazardous waste incineration", "Europe without Switzerland", -0.00136, "kilogram"),
            ("market for transport, freight, lorry, unspecified", "RER", 0.0209, "ton kilometer"),
            ("market group for transport, freight, train, fleet average", "RER", 0.0309, "ton kilometer"),
        ],
        "elementary": [
            ("Monoethanolamine", ("air",), 0.0000454, "kilogram"),
            ("Water", ("air",), 0.000473, "cubic meter"),
        ],
    },
    "C1": {
        "label": "C1 · By-product CO₂ (no source burden allocated; shared transport)",
        "entries": [
            ("market for carbon dioxide, in chemical industry", "GLO", 1.0, "kilogram"),
            ("market for transport, freight, lorry, unspecified", "RER", 0.0209, "ton kilometer"),
            ("market group for transport, freight, train, fleet average", "RER", 0.0309, "ton kilometer"),
        ],
        "elementary": [],
    },
    "C2": {
        "label": "C2 · Merchant liquid CO₂",
        "entries": [
            ("market for carbon dioxide, liquid", "RER", 1.0, "kilogram"),
        ],
        "elementary": [],
    },
}


def choices():
    return [{"code": code, "label": source["label"]} for code, source in SOURCES.items()]
