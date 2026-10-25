# SCM calculation core

The Python entry point is `run_calculation(payload)` in `engine.py` (also exported from `__init__.py`). It accepts an SCM process list and returns a foreground inventory, warnings, errors, and a process-chain summary. It does not access Flask, SQLite, or ecoinvent.

The calculation path is:

`engine.py` → `normalizer.py` → `modules/<process>.py` → `models/` where applicable → `chain.py`.

- `modules/` converts process inputs into per-kg outputs. Some simple process formulas live directly here; more detailed formulas live in `models/`.
- `chain.py` applies yields and allocation to the requested final dry mass. Physical totals and allocated totals are separate.
- `supporting_data/` stores reference properties, reaction data, equipment assumptions, grinding material references and fixed operation inventories. It has no dependency on models, input validation or API assembly. Source notes, proxy labels, derived-value tags and case-derived optional presets remain attached to their records.
- `process_settings/` defines each process's input fields, settings dataclasses and editable engineering assumptions, selecting reference values from `supporting_data/` where appropriate. `crushing.py`, `grinding.py`, `thermal_activation.py` and `carbonation.py` are process-specific; `separation.py` shares the same contract across sieving, sorting and screening; `recovery.py` shares yield/allocation fields. The website schema and calculation adapters use these same definitions.
- `parameters.py` parses and validates inputs and assembles the API schema. `units.py` holds shared unit conversion factors. `input_catalogue.py` assembles reference choices and defaults for the API; it contains no reference tables or calculation formulas. The response key remains `input_libraries` for existing frontend consumers.
- `supporting_data/thermal_reactions.py` maps selectable TGA reactions to loss channels and the author's four reference enthalpies. `modules/thermal_activation.py` resolves the selected reaction and validates interval inputs. A listed pure-reaction interval derives its reactant fraction stoichiometrically from full-interval gas loss and includes its reference heat automatically. Descriptive intervals do not infer reaction heat. Explicit `reaction_terms` take precedence, so heat is never added twice. Mg reactions require measured start/end temperatures because no universal window is specified.
- `models/retained_carbonation.py` owns the reusable carbonation equations. `modules/general_conditions_carbonation.py` turns operating conditions into a per-kg inventory. The supported `general_operating_v2` model records equipment electricity and process heat separately. Wet routes use the slurry fill fraction; dry and semi-dry routes use dry feed loading per nominal reactor volume.
- `process_settings/carbonation_defaults.py` contains the single set of carbonation engineering defaults used by the current web calculation. `process_settings/carbonation.py` defines parameter types and constraints, and reads the same defaults for the API schema and equation inputs. These defaults are not universal material properties: some initial values came from the author's SI and cases, and users should review them for another system.
- Carbonation credits quantified reaction heat at 100% utilization by default when a reaction phase or explicit heat value is provided; without either, no reaction heat is inferred. This credit offsets foreground sensible heating, not drying or hold losses.
Only the general Carbonation operating-conditions adapter is supported. Earlier article-specific formula adapters are not included.

## Reference data and settings

```text
calculation/
├── supporting_data/
│   ├── physical_constants.py      # CO2 molar mass and gravity
│   ├── material_properties.py     # heat capacities and water latent heat
│   ├── carbonation_reactions.py   # carbonation heat references and proxies
│   ├── thermal_reactions.py       # TGA reaction references and optional windows
│   ├── equipment.py               # adopted reactor reference configuration
│   ├── infrastructure.py          # product-basis grinding and plant-use coefficients
│   ├── grinding_materials.py      # Bond indices and sourced calibration anchors
│   ├── operation_inventories.py   # crushing, sieving, sorting and screening
│   ├── co2_supply.py              # optional CO2 energy-helper assumptions
│   └── version.py                # reference catalogue version
├── process_settings/              # inputs, validation rules and editable defaults
│   ├── carbonation_defaults.py    # shared web/Python engineering defaults
│   ├── carbonation.py             # parameter types, constraints and route presets
│   ├── grinding_defaults.py       # grinding regime and energy corrections
│   ├── grinding.py                # grinding input contract and parameter class
│   ├── thermal_activation_defaults.py # heat-model defaults and property selections
│   └── thermal_activation.py      # thermal input contract and parameter classes
├── models/                        # balances, energy equations and calibration
├── modules/                       # resolve inputs and produce inventory exchanges
├── input_catalogue.py             # assemble API choices
└── units.py                       # shared unit conversions
```

`models/grinding.py` calculates fine-grinding calibration coefficients from the
anchors in `supporting_data/grinding_materials.py`; those derived coefficients
are not stored as a second reference table. The carbonation operation presets
and settings dataclasses are in `process_settings/carbonation.py`.

The 10 m³ equipment reference in `supporting_data/equipment.py` retains its 1.0
reference fill fraction as source metadata. Calculations select the current
wet-route default of 0.8 from `process_settings/carbonation_defaults.py`; dry
loading is a different parameter. The
optional captured/liquefied CO2 energy helper uses `supporting_data/co2_supply.py`;
these values are not the web C0/C1/C2 supply inventories in `recipes/`.

Moving data does not change its scientific status. The P1/P10 temperature
windows and grinding anchors remain labelled case-derived presets, and pending
enthalpy citations remain pending. They can be overridden for a different route.

## Route defaults and LCIA

`grinding_defaults.py` supplies the same transition size, fine-grinding exponent
and energy correction factors to the input schema, calibration and equations.
The Bond work index is explicit or supplied by a selected material record; raw
`GrindingParams` and `grinding_energy_kwh_per_kg` no longer assume Wi = 10. The
latter helper still accepts kWh/US short ton explicitly and converts it to kWh/t;
its auxiliary factor now matches the web default of 1.15 instead of 1.10.

`thermal_activation_defaults.py` supplies heat-up and holding-loss assumptions
and selects property defaults from `supporting_data`. Activation temperature
and holding time are explicit route inputs. `ThermalActivationSettings` requires
`holding_time_h` as a keyword argument (zero is allowed); subsequent overrides
also use keywords. There is no implicit one-hour calculation. Existing web
inputs already require holding time.

TGA data use one format: nonoverlapping total-loss temperature intervals, each
reported relative to the same initial dry sample. The reaction selection assigns
the H2O/CO2 shares. The website has no TGA mode selector. Omitted, blank or explicit
`total_intervals` inputs remain accepted; `gas_channels` inputs are rejected rather
than reinterpreted as total loss.

`carbonation_defaults.py` separates common coefficients, wet-route defaults and
dry/semi-dry defaults. The operating-conditions adapter then resolves their
applicability: recycle applies to separated filtrate, cake moisture requires
separation, and the final moisture target applies when drying is enabled.
Chamber control uses nominal reactor volume, with its resolved duty passed to
the model as an explicit override. Unused channels retain zero/None states.

The public Python entry point `run_calculation()` uses exactly the same defaults
and route-resolution logic as the website. The low-level
`CarbonationProcessSettings` dataclass holds resolved equation inputs: reaction
time, reaction temperature, water ratio, dry loading (or explicit `None` for
wet-volume loading), recycle and the two moisture states must be supplied as
keyword arguments. `GeneralCarbonationProcess` requires these settings instead
of creating an implicit 24-hour scenario. Existing direct low-level callers
must supply these fields or use `run_calculation()` for web-style inputs.

The editable general dry/semi-dry loading default is 300 kg dry feed/m³ on nominal chamber volume: 10 m³ × 300 = 3,000 kg per batch. The editable 0.8 reactor fill fraction belongs to the wet route, where 10 m³ × 0.8 = 8 m³ occupied slurry volume. Wet feed mass uses the water-to-powder ratio and material densities. Dry loading does not use the wet fill fraction. Saved inputs are checked against the supported process, energy-scenario and input-default definitions. Numeric model-version and historical formula-version labels are not required; source references and effective calculation inputs remain recorded.

LCA characterization and mix design are a separate layer in `../recipes/calculation.py`; background ecoinvent factors are resolved in `../recipes/background.py` when locally configured.

## Equipment and compression inventories

The user-supplied `SI1-3_ParameterAndInventories.xlsx` is the source for the
equipment coefficients in `supporting_data/infrastructure.py`:

- Grinding defaults to 4.41e-7 kg equipment per kg dry ground product. This
  coefficient is independent of the electricity inventory's mass basis.
  `grinding_machine_kg_per_kg_product` overrides it; an explicitly supplied
  legacy `grinding_machine_kg_per_kg_processed` retains its feed-mass basis.
  Supplying both is rejected.
- Thermal activation uses 4.029e-14 unit/(kg dry product·h), multiplied by
  holding time, and links to `market for cement factory` (GLO).
- Carbonation uses 4.029e-13 unit/(kg dry product·h), multiplied by reaction
  time, and links to `market for concrete mixing factory` (GLO).

Factory coefficients are editable in the process settings. Each resulting
equipment exchange carries its unit, source and mass-normalization basis;
the serial chain then scales it to final product demand and applies allocation.
Sorting includes 0.00437 MJ diesel and 0.000353 m³ hydraulic excavation per
reference kg, using the selected sorting inventory basis.

Carbonation P3 includes both headspace charging and external makeup CO2
compression. Headspace electricity is divided by batch feed mass; makeup CO2
is already on a per-kg-feed basis and is not divided by batch mass again.
The two components are recorded separately. A direct P3 override replaces
their total. Drying retains the existing 80 K temperature-rise default.
