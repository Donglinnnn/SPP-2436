"""Read-only local ecoinvent catalogue; isolated, cached Brightway characterization.

Never import user runners, select their Brightway project, or modify its database.
Only server configuration can choose local paths. Activity codes, not row positions,
are the public selection keys. Integer IDs stay strings across the JSON boundary.
"""
import hashlib
import json
import os
import pickle
import re
import sqlite3
import subprocess
import sys
import tempfile
import zipfile
from functools import lru_cache
from pathlib import Path
from threading import Lock

from src.config import ROOT_DIR, background_setting, local_settings

_project_setting = background_setting('SCM_BW_PROJECT_DIR', 'project_dir')
PROJECT = Path(_project_setting).expanduser() if _project_setting else None
PYTHON = background_setting('SCM_BW_PYTHON', 'python') or sys.executable
DATABASE = background_setting('SCM_BW_DATABASE', 'database') or 'ecoinvent-3.12-cutoff'
DEFAULT_METHOD = ['ecoinvent-3.12', 'EF v3.1 no LT', 'climate change no LT', 'global warming potential (GWP100) no LT']
_method_setting = os.environ.get('SCM_BW_METHOD')
if _method_setting is not None:
    METHOD = json.loads(_method_setting)
else:
    METHOD = local_settings().get('background', {}).get('method', DEFAULT_METHOD)
if not isinstance(METHOD, list) or len(METHOD) < 2 or not all(isinstance(part, str) and part.strip() for part in METHOD):
    raise ValueError('background.method must be a nonempty TOML array of LCIA method labels')
LOCK = Lock()

DEFAULT_PROVIDERS = {
    'cement': ('market for cement, unspecified', 'Europe without Switzerland'),
    'sand': ('market for sand', 'CH'),
    'aggregate': ('market for gravel, crushed', 'CH'),
    'water': ('market for tap water', 'Europe without Switzerland'),
    'electricity': ('market for electricity, medium voltage', 'DE'),
    'heat': ('market for heat, district or industrial, natural gas', 'Europe without Switzerland'),
    'diesel': ('market for diesel, burned in building machine', 'GLO'),
    'machine': ('market for industrial machine, heavy, unspecified', 'RER'),
    'digger': ('excavation, hydraulic digger', 'RER'),
    'sorting': ('sorting facility construction, for construction waste', 'RoW'),
    'thermal_factory': ('market for cement factory', 'GLO'),
    'carbonation_factory': ('market for concrete mixing factory', 'GLO'),
    'wastewater': ('market for wastewater, average', 'Europe without Switzerland'),
    'co2_supply': ('market for carbon dioxide, in chemical industry', 'GLO'),
}
PROVIDERS = DEFAULT_PROVIDERS.copy()
_overrides = local_settings().get('background', {}).get('providers', {})
if not isinstance(_overrides, dict):
    raise ValueError('background.providers must be a TOML table')
for _key, _entry in _overrides.items():
    if _key not in PROVIDERS or not isinstance(_entry, dict) or not all(
        isinstance(_entry.get(field), str) and _entry[field].strip() for field in ('name', 'location')
    ):
        raise ValueError(f'Invalid background provider override: {_key}')
    PROVIDERS[_key] = (_entry['name'], _entry['location'])
_freight_setting = local_settings().get('background', {}).get('default_freight', {})
if not isinstance(_freight_setting, dict) or not set(_freight_setting).issubset({'name', 'location'}):
    raise ValueError('background.default_freight must contain name and location strings')
DEFAULT_FREIGHT = (
    _freight_setting.get('name', 'market for transport, freight, lorry, unspecified'),
    _freight_setting.get('location', 'RER'),
)
if not all(isinstance(value, str) and value.strip() for value in DEFAULT_FREIGHT):
    raise ValueError('background.default_freight must contain name and location strings')


class BackgroundUnavailable(ValueError):
    pass


def configured_project() -> Path:
    if PROJECT is None:
        raise BackgroundUnavailable('Local ecoinvent is not configured. Set SCM_BW_PROJECT_DIR or local_config.toml.')
    if not PROJECT.is_dir():
        raise BackgroundUnavailable('Configured Brightway project directory does not exist.')
    return PROJECT


def connection():
    path = configured_project() / 'lci/databases.db'
    if not path.exists():
        raise BackgroundUnavailable('Local ecoinvent database is unavailable; no placeholder factors are used.')
    conn = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def record(row):
    if row is None:
        raise BackgroundUnavailable('The selected ecoinvent activity is unavailable.')
    data = pickle.loads(row['data'])  # Trusted, local Brightway database only.
    return dict(id=str(row['id']), code=row['code'], database=row['database'], name=row['name'],
                location=row['location'], unit=data.get('unit'), reference_product=row['product'])


def activity(code):
    with connection() as conn:
        return record(conn.execute('SELECT * FROM activitydataset WHERE database=? AND code=?', (DATABASE, code)).fetchone())


@lru_cache(maxsize=64)
def exact_activity(name, location, unit):
    """Resolve one authored inventory entry without geographic substitution."""
    with connection() as conn:
        rows = conn.execute('SELECT * FROM activitydataset WHERE database=? AND name=? AND location=?',
                            (DATABASE, name, location)).fetchall()
    matches = [source for row in rows if (source := record(row))['unit'] == unit]
    if len(matches) != 1:
        raise BackgroundUnavailable(f'Expected one {unit} activity for {name} ({location}), found {len(matches)}.')
    return matches[0]


@lru_cache(maxsize=16)
def exact_elementary(name, categories, unit):
    """Resolve an authored elementary emission by compartment and unit."""
    with connection() as conn:
        rows = conn.execute("SELECT * FROM activitydataset WHERE database!=? AND name=? AND type='emission'",
                            (DATABASE, name)).fetchall()
    matches = []
    for row in rows:
        data = pickle.loads(row['data'])  # Trusted local Brightway database only.
        if tuple(data.get('categories', ())) == categories and data.get('unit') == unit:
            matches.append(record(row))
    if len(matches) != 1:
        raise BackgroundUnavailable(f'Expected one {unit} elementary flow for {name} to {categories}, found {len(matches)}.')
    return matches[0]


def recipe_material(code):
    """A mass-based ecoinvent market that can be added directly to a mix."""
    if not isinstance(code, str) or not code:
        raise ValueError('Select a material from the local ecoinvent catalogue')
    with connection() as conn:
        row = conn.execute('SELECT * FROM activitydataset WHERE database=? AND code=?', (DATABASE, code)).fetchone()
    if row is None:
        raise ValueError('Selected direct material is not in the local ecoinvent catalogue')
    source = record(row)
    if not source['name'].startswith('market for ') or source['unit'] != 'kilogram':
        raise ValueError('Direct mix materials must be kilogram-based ecoinvent markets')
    return source


def search_recipe_materials(query, limit=30):
    """Bounded, read-only search; activity codes are resolved again at calculation."""
    if not isinstance(query, str) or len(query.strip()) < 2:
        return []
    normalized = query.strip()[:100]
    normalized = {'ggbs': 'ground granulated blast furnace slag',
                  'ggbfs': 'ground granulated blast furnace slag',
                  'superplasticizer': 'plasticiser'}.get(normalized.lower(), normalized)
    term = normalized.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
    with connection() as conn:
        rows = conn.execute(
            "SELECT * FROM activitydataset WHERE database=? AND name LIKE 'market for %' "
            "AND (name LIKE ? ESCAPE '\\' OR product LIKE ? ESCAPE '\\') "
            "ORDER BY name,location,code LIMIT 600", (DATABASE, f'%{term}%', f'%{term}%')).fetchall()
    return [source for row in rows if (source := record(row))['unit'] == 'kilogram'][:limit]


@lru_cache(maxsize=1)
def concrete_references():
    """Selectable factory-gate concrete activities with one exact MPa class."""
    with connection() as conn:
        rows = conn.execute(
            "SELECT * FROM activitydataset WHERE database=? AND name LIKE 'concrete production,%' "
            "ORDER BY name,location,code", (DATABASE,)).fetchall()
    choices = []
    for row in rows:
        source = record(row)
        match = re.match(r'^concrete production,\s*(\d+(?:\.\d+)?)MPa(?:,|$)', source['name'])
        if not match or source['unit'] != 'cubic meter' or re.search(r'\bRC-[CM]\b|recycled', source['name'], re.I):
            continue
        comment = str(pickle.loads(row['data']).get('comment', ''))
        source['strength_mpa'] = float(match.group(1))
        source['age_days'] = 28 if re.search(r'\b(?:compressive\s+)?strength\s+at\s+28\s+days\b', comment, re.I) else None
        choices.append(source)
    return sorted(choices, key=lambda item: (item['strength_mpa'],
        'for building construction' not in item['name'], 'Portland' not in item['name'],
        item['location'], item['name']))


def concrete_reference(code):
    """Resolve an explicitly selected production activity without substitution."""
    if not isinstance(code, str) or not code:
        raise ValueError('Choose an ecoinvent concrete production reference')
    source = next((item for item in concrete_references() if item['code'] == code), None)
    if source is None:
        raise ValueError('The selected concrete production reference is unavailable')
    return source.copy()


@lru_cache(maxsize=1)
def catalogue():
    with connection() as conn:
        cement = [record(r) for r in conn.execute('SELECT * FROM activitydataset WHERE database=? AND name LIKE ? ORDER BY name,location,code', (DATABASE, 'market for cement,%'))]
        fixed = {}
        for key, (name, loc) in PROVIDERS.items():
            rows = conn.execute('SELECT * FROM activitydataset WHERE database=? AND name=? AND location=?', (DATABASE, name, loc)).fetchall()
            if len(rows) != 1:
                raise BackgroundUnavailable(f'Expected one provider for {name} ({loc}), found {len(rows)}. No automatic substitute.')
            fixed[key] = record(rows[0])
            if key in {'thermal_factory', 'carbonation_factory'} and fixed[key]['unit'] != 'unit':
                raise BackgroundUnavailable(f'{key}: expected a factory provider measured in unit.')
    return dict(status='connected', database=DATABASE, method=METHOD, cements=cement, providers=fixed,
                source=f'Read from the local licensed {DATABASE} database')


@lru_cache(maxsize=1)
def lca_catalogue():
    """Selectable, unit-checked providers; listing never runs characterization."""
    from .co2_sources import choices as co2_choices
    from .electricity_scenarios import ENERGY_SCENARIO_VERSION, SCENARIOS
    with connection() as conn:
        transport = [record(r) for r in conn.execute(
            "SELECT * FROM activitydataset WHERE database=? AND name LIKE 'market for transport, freight,%' "
            "AND name NOT LIKE '%reefer%' AND name NOT LIKE '%refrig%' "
            "ORDER BY location,name,code", (DATABASE,))]
    transport = [r for r in transport if r['unit'] == 'ton kilometer']
    default = [r for r in transport if (r['name'], r['location']) == DEFAULT_FREIGHT]
    if len(default) != 1:
        raise BackgroundUnavailable('Configured default freight market is unavailable; choose its exact name/location in local_config.toml.')
    energy_scenarios = [dict(code=key, label=value['label'],
                             electricity_name=value['name'], electricity_location=value['location'],
                             heat_name=value['heat_name'], heat_location=value['heat_location'])
                        for key, value in SCENARIOS.items()]
    return dict(database=DATABASE, method=METHOD,
                energy_scenario_version=ENERGY_SCENARIO_VERSION,
                energy_scenarios=energy_scenarios,
                electricity_scenarios=energy_scenarios,
                transport=transport,
                co2_sources=co2_choices(),
                defaults=dict(electricity_scenario='E0',
                              electricity_code=exact_activity('market for electricity, medium voltage', 'DE', 'kilowatt hour')['code'],
                              heat_code=exact_activity(SCENARIOS['E0']['heat_name'],
                                                       SCENARIOS['E0']['heat_location'], 'megajoule')['code'],
                              transport_code=default[0]['code']))


def selected_provider(kind, code):
    if not isinstance(code, str):
        raise ValueError(f'Choose an {kind} activity code from the local ecoinvent catalogue')
    if kind == 'electricity':
        source = activity(code)
        if source['unit'] != 'kilowatt hour' or not source['reference_product'].startswith('electricity') or not source['name'].startswith(
            ('market for electricity,', 'market group for electricity,', 'electricity production,')
        ):
            raise ValueError('The saved electricity activity is not a supported local electricity provider.')
        return source
    match = next((r for r in lca_catalogue()[kind] if r['code'] == code), None)
    if match is None:
        raise ValueError(f'The selected {kind} activity is not in the supported local catalogue; select it again.')
    return match


def sensitivity_energy(scenario):
    """Resolve the authored electricity/heat pair for one paper E scenario.

    Returns (electricity provider, fixed electricity factor or None,
    heat provider, fixed heat factor or None). Heat markets use megajoules;
    callers convert kWh of process heat to MJ before applying their factor.
    """
    from .electricity_scenarios import DELIVERY_CODES, SCENARIOS
    if scenario not in SCENARIOS:
        raise ValueError('Choose E0, E1 or E2 as the paired energy scenario')
    definition = SCENARIOS[scenario]
    heat = exact_activity(definition['heat_name'], definition['heat_location'], 'megajoule')
    heat = dict(heat, scenario=scenario)
    if scenario != 'E1':
        electricity = exact_activity(definition['name'], definition['location'], 'kilowatt hour')
        return dict(electricity, scenario=scenario, label=definition['label']), None, heat, None
    if DATABASE != 'ecoinvent-3.12-cutoff' or METHOD != DEFAULT_METHOD:
        raise BackgroundUnavailable('E1 paper factor requires ecoinvent 3.12 cut-off and EF v3.1 no LT GWP100.')
    for code, name in DELIVERY_CODES.items():
        source = activity(code)
        if (source['name'], source['location'], source['unit']) != (name, 'DE', 'kilowatt hour'):
            raise BackgroundUnavailable('The local electricity delivery chain differs from paper SI S3.')
    source = activity(definition['generation_code'])
    if (source['name'], source['location'], source['unit']) != (definition['generation_name'], 'DE', 'kilowatt hour'):
        raise BackgroundUnavailable('The local E1 generation provider differs from paper SI S3.')
    electricity = dict(code='paper-E1', name=definition['name'], location='DE',
                       unit='kilowatt hour', reference_product='electricity, medium voltage',
                       scenario=scenario, label=definition['label'],
                       source='Paper SI S3 derived delivered supply')
    return electricity, definition['factor'], heat, None


def sensitivity_electricity(scenario):
    """Compatibility accessor for callers that only need the electric provider."""
    electricity, fixed_factor, _, _ = sensitivity_energy(scenario)
    return electricity, fixed_factor


@lru_cache(maxsize=1)
def resolved_packages():
    """Find the configured database, its biosphere, and LCIA package by project metadata."""
    project = configured_project()
    try:
        methods = json.loads((project / 'methods.json').read_text())
        matches = [metadata for labels, metadata in methods if labels == METHOD]
        if len(matches) != 1:
            raise BackgroundUnavailable(f'Configured LCIA method has {len(matches)} exact matches in this Brightway project.')
        metadata = matches[0]
        if not metadata.get('database') or not metadata.get('abbreviation') or metadata.get('num_cfs', 0) <= 0:
            raise BackgroundUnavailable('Configured LCIA method has incomplete Brightway metadata.')
        unit = str(metadata.get('unit', '')).lower().replace('₂', '2')
        if 'co2' not in unit or not any('gwp100' in label.lower() for label in METHOD):
            raise BackgroundUnavailable('This website requires a GWP100 climate-change method in kg CO2 equivalent.')
        wanted = {DATABASE, metadata['database']}
        found = {name: [] for name in wanted}
        for path in (project / 'processed').glob('*.zip'):
            with zipfile.ZipFile(path) as archive:
                package_name = json.loads(archive.read('datapackage.json'))['name']
            if package_name in found:
                found[package_name].append(path)
        for name, paths in found.items():
            if len(paths) != 1:
                raise BackgroundUnavailable(f'Expected one processed Brightway package for {name}; found {len(paths)}.')
        method_package = project / 'processed' / f"{metadata['abbreviation']}.zip"
        if not method_package.is_file():
            raise BackgroundUnavailable('Processed package for the configured LCIA method is missing.')
        return [found[DATABASE][0], found[metadata['database']][0], method_package]
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        if isinstance(exc, BackgroundUnavailable):
            raise
        raise BackgroundUnavailable('Brightway method or processed-package metadata is missing or invalid.') from exc


def fingerprint():
    project = configured_project()
    files = resolved_packages() + [project / 'lci/databases.db', project / 'methods.json']
    try:
        raw = [(str(p), p.stat().st_size, p.stat().st_mtime_ns) for p in files]
    except OSError as exc:
        raise BackgroundUnavailable('A required local ecoinvent/method package is unavailable; no placeholder factors are used.') from exc
    return hashlib.sha256(json.dumps([DATABASE, METHOD, raw]).encode()).hexdigest()


def run_worker(records, elementary_records=()):
    """Characterize in a temporary Brightway project; never write the licensed source."""
    try:
        result = subprocess.run([PYTHON, str(Path(__file__).with_name('factor_worker.py'))],
            input=json.dumps(dict(packages=[str(path) for path in resolved_packages()], records=records,
                                 elementary_records=elementary_records)),
            capture_output=True, text=True, timeout=90,
            env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', 'OMP_NUM_THREADS': '1', 'OPENBLAS_NUM_THREADS': '1'})
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise BackgroundUnavailable('Brightway characterization could not run; check the configured Python and packages.') from exc
    if result.returncode:
        raise BackgroundUnavailable('Brightway characterization failed; no numerical LCA total is reported. ' + result.stderr[-600:])
    try:
        return json.loads(result.stdout)
    except (ValueError, KeyError) as exc:
        raise BackgroundUnavailable('Brightway worker returned an invalid response.') from exc


def factors(records):
    """Return EF GWP per provider reference unit, with cache invalidation."""
    if not records:
        return {}
    runtime = ROOT_DIR / 'data/recipe_runtime'
    runtime.mkdir(parents=True, exist_ok=True)
    key = fingerprint()
    cache_path = runtime / 'factors.json'
    with LOCK:
        try:
            cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
        except (OSError, ValueError):
            cache = {}  # A damaged generated cache is rebuilt from the database.
        scores = cache.get('scores', {}) if cache.get('fingerprint') == key else {}
        missing = {r['code']: r for r in records if r['code'] not in scores}
        if missing:
            answer = run_worker(list(missing.values()))
            scores.update(answer['scores'])
            # Generated cache, never a source-code or source-database mutation.
            with tempfile.NamedTemporaryFile('w', dir=runtime, delete=False) as handle:
                json.dump(dict(fingerprint=key, method=METHOD, scores=scores, validation=answer['validation']), handle)
                temp = Path(handle.name)
            temp.replace(cache_path)
        return {r['code']: scores[r['code']] for r in records}


@lru_cache(maxsize=16)
def _elementary_factors_cached(background_fingerprint, identifiers):
    reference = catalogue()['providers']['electricity']
    records = [dict(code=code, id=identifier) for code, identifier in identifiers]
    return run_worker([reference], records)['elementary_scores']


def elementary_factors(records):
    """Characterization factors for elementary emissions in the active method."""
    if not records:
        return {}
    identifiers = tuple(sorted((source['code'], source['id']) for source in records))
    return _elementary_factors_cached(fingerprint(), identifiers).copy()


def preparation():
    configured = background_setting('SCM_PREPARATION_INVENTORY', 'preparation_inventory')
    path = Path(configured).expanduser() if configured else Path(__file__).with_name('preparation_inventory.json')
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise BackgroundUnavailable('The local licensed mixing inventory is unavailable or invalid.') from exc


def preparation_gwp():
    # The process-only mixing inventory was independently characterized against this method.
    # Recompute its signed exchange sum; do not include recipe constituents twice.
    data = preparation()
    if not isinstance(data, dict) or data.get('lcia_method') != METHOD:
        raise BackgroundUnavailable('The mixing inventory uses another LCIA method; it cannot be combined with this recipe.')
    try:
        return dict(gwp_kg_co2e_m3=sum(r['amount'] * r['gwp_per_unit'] for r in data['retained_exchanges']),
                    electricity_kwh_m3=sum(r['amount'] for r in data['retained_exchanges'] if r.get('role') == 'electricity'),
                    inventory_name='Mixing', reference_product='Fresh mixture preparation',
                    reference_unit='cubic meter', exchange_count=len(data['retained_exchanges']),
                    source=data['source'], source_sha256=data['source_sha256'], method=data['lcia_method'],
                    status='characterized_mixing_inventory', water_split=data['water_split'])
    except (KeyError, TypeError, ValueError) as exc:
        raise BackgroundUnavailable('The mixing inventory has an invalid structure.') from exc


def preparation_status():
    """Report optional inventory availability without blocking direct-ingredient recipes."""
    try:
        return dict(available=True, **preparation_gwp())
    except BackgroundUnavailable as exc:
        return dict(available=False, reason=str(exc))
