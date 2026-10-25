# Recipe calculation and LCIA

- `calculation.py`: SCM characterization, ingredient totals, mixing, delivery,
  volume conversion and strength comparisons.
- `supporting_data/mixing.py`: supplied foam-mixing electricity and machine
  inventory quantities. Ordinary mixing is already loaded from a separate local
  inventory file by `background.preparation()`.
- `settings.py`: editable density, air, recovery and mixing-conversion defaults.
  The calculation and `/recipe-schema` use this one source; the browser uses the
  schema for initial inputs and missing saved-input values. Explicit saved values
  take precedence. Foam reference-mass and machine-conversion assumptions remain
  provisional, not verified universal values.
  `FORM_DEFAULTS` and `STARTER_AMOUNTS_KG` describe the initial browser form only;
  the 700 kg cement / 350 kg water starter is not a model fallback or reference
  concrete. The 28-day performance criterion remains part of the indicator.
- `exchange_mapping.py`: foreground-flow classification and background-provider
  mapping. These are linking rules, not material properties.
  Thermal-activation and carbonation factory exchanges map to distinct
  unit-based markets with conversion factor 1; process heat alone converts
  kWh to MJ using 3.6.
- `../calculation/units.py`: shared conversion factors, including kWh to MJ.
  Characterization and source recording use the same factor.
- `model_contract.py`: checks energy definitions and supported inputs.
- `background.py`: read-only provider resolution and characterization.
- `recording.py`: records the providers and quantity conversions actually used.

The application runs one current model. There is no numeric `MODEL_VERSION`
requirement; a leftover `model_version` field in saved data is ignored, and new
projects and calculated results do not add it. Energy-scenario and input-default
identifiers still describe the definitions used for stored data. Historical
formula-version labels are no longer emitted or required. Calculation inputs,
quantities, provider identities and source references remain recorded.
