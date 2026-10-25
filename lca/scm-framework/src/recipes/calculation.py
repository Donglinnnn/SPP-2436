"""Ingredient mass → foreground/background GWP → volume → matched strength.

No cement displacement credit: cement demand is entered explicitly in the recipe.
No SCM double counting: a material item's per-kg score already contains its route.
"""
import copy
import math

from src.calculation import run_calculation
from src.calculation.units import KWH_TO_MJ
from src.calculation.process_settings.carbonation import (
    INPUT_DEFAULTS_VERSION,
)
from . import background as bg
from .co2_sources import SOURCES as CO2_SOURCES
from .electricity_scenarios import ENERGY_SCENARIO_VERSION
from .model_contract import IncompatibleModelError, require_current_settings, require_current_processes
from .recording import finalize_lcia_recording
from .exchange_mapping import FLOW_MAP, PHYSICAL_ONLY
from .settings import DEFAULT_DENSITIES_KG_PER_M3, DEFAULTS
from .supporting_data.mixing import FOAM_ELECTRICITY_KWH, FOAM_MACHINE_UNIT


def require_current_energy_model(pathway):
    """Reject routes whose saved version cannot be interpreted by this model."""
    if not isinstance(pathway, dict):
        raise ValueError('A pathway input record is required')
    settings = require_current_settings(pathway.get('lca_settings'), label='Route')
    require_current_processes(pathway.get('processes'), label='Route')
    return settings


def number(value, label, minimum=0, positive=False):
    if isinstance(value, bool) or value is None or value == '':
        raise ValueError(f'{label} must be a number')
    try:
        n = float(value)
    except (TypeError, ValueError):
        raise ValueError(f'{label} must be a number')
    if not math.isfinite(n) or n < minimum or (positive and n <= 0):
        raise ValueError(f'{label} must be finite and {"greater than zero" if positive else "at least " + str(minimum)}')
    return n


def scm_foreground(pathway):
    """Validate a reusable SCM without accessing the background database."""
    request = copy.deepcopy(pathway)
    require_current_energy_model(request)
    material = request.get('material') or {}
    if isinstance(material, dict) and material.get('feedstock_burden_rule') not in (None, '', 'excluded waste burden'):
        raise ValueError('This material module supports the declared waste cut-off boundary only. Included/allocated feedstock upstream burdens need an explicit inventory before saving a characterized item.')
    request['functional_unit_kg'] = 1
    result = run_calculation(request)
    if not result.ok:
        raise ValueError('; '.join(result.errors))
    if result.summary.get('status') != 'complete':
        raise ValueError('A complete serial pathway is required to create a material item')
    amount = result.summary['allocated_totals']
    unknown = {k for k,v in amount.items() if v and k not in FLOW_MAP and k not in PHYSICAL_ONLY
               and k not in {'co2_emitted_kg','co2_stored_kg','co2_makeup_kg'}}
    if unknown:
        raise ValueError('Unmapped inventory flows: ' + ', '.join(sorted(unknown)))
    return request, result


def lca_settings(pathway, has_carbonation=True):
    settings = require_current_energy_model(pathway)
    transport = settings.get('transport', {})
    if not isinstance(transport, dict) or set(transport) - {'waste_to_process'}:
        raise ValueError('SCM route transport may contain only waste_to_process')
    for key, leg in transport.items():
        if not isinstance(leg, dict) or not isinstance(leg.get('enabled', False), bool):
            raise ValueError(f'{key}: transport selection must be boolean')
        if leg.get('enabled'):
            if leg.get('activity_code') is not None and (not isinstance(leg['activity_code'], str) or not leg['activity_code']):
                raise ValueError(f'{key}: choose a freight activity code')
            number(leg.get('distance_km'), key + ' distance (km)', positive=True)
            if number(leg.get('moisture_percent', 0), key + ' wet-basis moisture (%)') >= 100:
                raise ValueError('Transport moisture must be below 100% of wet cargo mass')
    source = settings.get('co2_source')
    if source is not None and source not in CO2_SOURCES:
        raise ValueError('Choose C0, C1 or C2 as the CO2 source')
    if 'co2_supply_factor' in settings:
        raise ValueError('External CO2 supply must use C0, C1 or C2; a supplied factor is unsupported.')
    if settings.get('electricity_scenario') is not None and settings['electricity_scenario'] not in ('E0', 'E1', 'E2'):
        raise ValueError('Choose E0, E1 or E2 as the paired energy scenario')
    if any(settings.get(key) is not None for key in
           ('electricity_code', 'heat_code', 'electricity_source', 'heat_source', 'heat_market')):
        raise ValueError('The paired energy model requires one E0/E1/E2 choice, not independent electricity or heat providers')
    if 'recipe_transport' in settings:
        validate_recipe_transport(settings['recipe_transport'])
    return settings


def characterize_scm(pathway):
    request, result = scm_foreground(pathway)
    has_carbonation = any(step.process_name == 'Carbonation' for step in result.items)
    settings = lca_settings(request, has_carbonation=has_carbonation)
    amount = result.summary['allocated_totals']
    source_key = settings.get('co2_source', 'C0') if has_carbonation else None
    co2_source = CO2_SOURCES.get(source_key)
    source_activity_rows = []
    source_elementary_rows = []
    if co2_source:
        source_activity_rows = [(amount, unit, bg.exact_activity(name, location, unit))
                                for name, location, amount, unit in co2_source['entries']]
        source_elementary_rows = [(amount, unit, bg.exact_elementary(name, categories, unit))
                                  for name, categories, amount, unit in co2_source['elementary']]
    providers = dict(bg.catalogue()['providers'])
    energy_scenario = settings.get('electricity_scenario') or 'E0'
    electricity, fixed_electricity_factor, heat, fixed_heat_factor = bg.sensitivity_energy(energy_scenario)
    if electricity['unit'] != 'kilowatt hour' or heat['unit'] != 'megajoule':
        raise ValueError('Paired energy providers must supply electricity in kWh and process heat in MJ')
    providers.update(electricity=electricity, heat=heat)
    legs = []
    for key, label, mass, allocation in [
        ('waste_to_process', 'Waste → processing facility', result.summary['initial_feed_required_kg'], result.summary['steps'][0]['burden_allocation_factor']),
    ]:
        config = settings.get('transport', {}).get(key, {})
        if not config.get('enabled', False):
            continue
        code = config.get('activity_code') or bg.lca_catalogue()['defaults']['transport_code']
        freight_provider = bg.selected_provider('transport', code)
        distance = number(config['distance_km'], label + ' distance', positive=True)
        moisture = number(config.get('moisture_percent', 0), label + ' moisture')
        wet_mass = mass / (1 - moisture / 100)
        tkm = wet_mass / 1000 * distance
        if not math.isfinite(tkm):
            raise ValueError('Transport demand overflow')
        legs.append(dict(key=key, label=label, dry_mass_kg=mass, wet_mass_kg=wet_mass,
            moisture_percent=moisture, distance_km=distance, ton_km=tkm,
            allocation_factor=allocation, allocated_ton_km=tkm*allocation, provider=freight_provider))
    fixed_energy_factors = {'electricity': fixed_electricity_factor, 'heat': fixed_heat_factor}
    needed = [providers[p] for key,(p,_) in FLOW_MAP.items()
              if amount.get(key,0) and fixed_energy_factors.get(p) is None]
    needed.extend(leg['provider'] for leg in legs)
    if amount.get('co2_makeup_kg', 0):
        needed.extend(provider for _, _, provider in source_activity_rows)
    scores = bg.factors(needed)
    if fixed_electricity_factor is not None:
        scores[providers['electricity']['code']] = fixed_electricity_factor
    if fixed_heat_factor is not None:
        scores[providers['heat']['code']] = fixed_heat_factor
    source_components = []
    if co2_source:
        elementary_scores = bg.elementary_factors([provider for _, _, provider in source_elementary_rows]) if amount.get('co2_makeup_kg', 0) else {}
        for kind, entries, source_scores in [('technosphere', source_activity_rows, scores),
                                              ('elementary', source_elementary_rows, elementary_scores)]:
            for quantity, unit, provider in entries:
                factor = source_scores.get(provider['code'], 0) if amount.get('co2_makeup_kg', 0) else 0
                source_components.append(dict(kind=kind, provider=provider, amount=quantity, unit=unit,
                                              factor=factor, gwp=quantity * factor))
        supply = math.fsum(row['gwp'] for row in source_components)
    else:
        supply = 0
    source_label = co2_source['label'] if co2_source else None
    source_provider = (dict(name=source_label, location='Author inventory')
                       if has_carbonation else None)

    def characterize_flows(flows):
        rows = []
        for key,(provider,multiplier) in FLOW_MAP.items():
            if flows.get(key,0):
                source = providers[provider]
                value = flows[key] * multiplier
                # Waste-treatment reference products have negative scores/demands.
                sign = -1 if provider == 'wastewater' else 1
                factor = scores[source['code']]
                rows.append(dict(flow=key, amount=value*sign, unit=source['unit'],
                    provider=source, factor=factor, gwp=value*sign*factor))
        rows.extend(dict(flow=key, amount=flows.get(key,0), factor=factor,
            gwp=flows.get(key,0)*factor, unit='kg') for key,factor in
            [('co2_emitted_kg',1), ('co2_stored_kg',-1)])
        if has_carbonation:
            rows.append(dict(flow='co2_makeup_kg', amount=flows.get('co2_makeup_kg',0), factor=supply,
                gwp=flows.get('co2_makeup_kg',0)*supply, unit='kg', provider=source_provider))
        return rows

    contributions = characterize_flows(amount)
    processes = []
    for step in result.summary['steps']:
        rows = characterize_flows(step['allocated_contributions'])
        processes.append(dict(process_name=step['process_name'], process_order=step['process_order'],
            required_input_kg=step['required_input_kg'], required_output_kg=step['required_output_kg'],
            allocation_factor=step['burden_allocation_factor'], gwp=math.fsum(r['gwp'] for r in rows), contributions=rows))
    for leg in legs:
        leg['factor'] = scores[leg['provider']['code']]
        leg['gwp'] = leg['allocated_ton_km'] * leg['factor']
        contributions.append(dict(flow=leg['key'], amount=leg['allocated_ton_km'], unit='ton kilometer',
            provider=leg['provider'], factor=leg['factor'], gwp=leg['gwp']))
    total = math.fsum(r['gwp'] for r in contributions)
    if not math.isfinite(total):
        raise ValueError('SCM GWP overflow')
    # Store resolved defaults so snapshots remain explicit and reproducible.
    request['lca_settings'] = dict(
        energy_scenario_version=ENERGY_SCENARIO_VERSION,
        input_defaults_version=INPUT_DEFAULTS_VERSION,
        transport={key: next((dict(enabled=True, activity_code=leg['provider']['code'],
            distance_km=leg['distance_km'], moisture_percent=leg['moisture_percent']) for leg in legs if leg['key']==key),
            dict(enabled=False)) for key in ('waste_to_process',)})
    if has_carbonation:
        request['lca_settings']['co2_source'] = source_key
    request['lca_settings']['electricity_scenario'] = energy_scenario
    if 'recipe_transport' in settings:
        request['lca_settings']['recipe_transport'] = copy.deepcopy(settings['recipe_transport'])
    delivery = 0
    foreground = result.to_dict()
    records = finalize_lcia_recording(
        foreground['records'], settings=request['lca_settings'], processes=processes,
        transport=legs, source_components=source_components,
        electricity_source=providers['electricity'], heat_source=providers['heat'], method=bg.METHOD)
    energy_contributions = {flow: next((row['gwp'] for row in contributions if row['flow'] == flow), 0)
                            for flow in ('electricity_kwh', 'heat_kwh')}
    energy = dict(electricity_kwh=amount.get('electricity_kwh', 0),
                  heat_kwh=amount.get('heat_kwh', 0),
                  heat_mj=amount.get('heat_kwh', 0) * KWH_TO_MJ,
                  electricity_gwp_kg_co2e=energy_contributions['electricity_kwh'],
                  heat_gwp_kg_co2e=energy_contributions['heat_kwh'],
                  kwh_to_mj=KWH_TO_MJ)
    return dict(pathway=request, foreground=foreground, lcia_recording=records['C'],
        gwp_kg_co2e_kg=total, contributions=contributions,
        production_gwp_kg_co2e_kg=total-delivery, delivery_gwp_kg_co2e_kg=delivery,
        transport=legs, process_contributions=processes, energy_scenario=energy_scenario,
        energy_scenario_version=ENERGY_SCENARIO_VERSION,
        input_defaults_version=INPUT_DEFAULTS_VERSION, energy=energy,
        electricity_source=providers['electricity'], heat_source=providers['heat'],
        co2_supply_factor=supply, co2_source=source_key, co2_source_label=source_label,
        co2_source_inventory=source_components, method=bg.METHOD, background_fingerprint=bg.fingerprint(),
        boundary='Selected waste-processing route under cut-off; '
            + 'SCM delivery excluded; waste transport '
            + ('included' if any(leg['key']=='waste_to_process' for leg in legs) else 'excluded'),
        assumptions=[f"SCM equipment electricity: {providers['electricity'].get('label', providers['electricity']['name'])} ({providers['electricity']['location']}).",
            f"SCM process heat: {providers['heat']['name']} ({providers['heat']['location']}); foreground kWh converted to MJ by ×3.6 before characterization. Heating and drying are excluded from equipment electricity.",
            ('E1 uses the SI S3 derived lignite supply delivered at medium voltage; its grid and transformation are included once.'
             if energy_scenario == 'E1' else 'E0 uses the German medium-voltage electricity market.' if energy_scenario == 'E0'
             else 'E2 uses the renewable electricity market and future-heat market proxy; the heat proxy is not a validated high-temperature process-heat technology.'),
            'Only explicit foreground electricity and process-heat providers vary with E0/E1/E2; embedded upstream energy and mixture preparation stay fixed.',
            *([f'Conditional paper CO2 convention: released CO2 +1; retained CO2 −1; external makeup uses {source_label} ({supply:.6g} kg CO2e/kg CO2).',
               'CO2 makeup loss is an alias of emitted CO2, never counted twice.'] if has_carbonation else []),
            'Optional inbound waste transport: dry cargo tonnes × one-way loaded distance. ecoinvent freight includes average loading/empty returns; distance is not doubled. Inbound burden follows the route allocation.',
            'SCM delivery is selected and accounted for separately in a recipe.',
            'Solid-reject treatment, previous-life feedstock burdens, use phase and end of life are excluded. GWP100 only, not a full multi-indicator LCA.'])


def calculate_scm_lca(payload):
    """Preserve the existing foreground contract; add characterized per-kg results."""
    require_current_energy_model(payload)
    foreground = run_calculation(payload)
    result = foreground.to_dict()
    if not foreground.ok:
        return result
    snapshot = characterize_scm(payload)
    fu = foreground.summary['functional_unit_kg']
    total = snapshot['gwp_kg_co2e_kg'] * fu
    if not math.isfinite(total):
        raise ValueError('Requested LCA total overflow')
    # The SCM snapshot is characterized per 1 kg dry product. Keep its links on
    # that explicit basis beside the caller's requested-FU foreground records.
    result['records']['C']['lcia_resolution'] = copy.deepcopy(snapshot['lcia_recording'])
    result['records']['C']['lcia_status'] = 'calculated'
    result['records']['C']['status'] = 'foreground_with_lcia_resolution'
    result['lca'] = {k:v for k,v in snapshot.items() if k not in ('foreground','pathway','lcia_recording')}
    result['lca'].update(functional_unit_kg=fu, gwp_kg_co2e=total, breakdown_basis='per 1 kg dry SCM')
    result['summary'].update(calculation_kind='lca_climate_change', lcia_status='calculated')
    return result


def recycled_inventory(yield_fraction=DEFAULTS['recycled_yield_fraction']):
    y = number(yield_fraction, 'Recycled aggregate target yield', positive=True)
    if y > 1:
        raise ValueError('Recycled aggregate target yield cannot exceed 100%')
    # This is an independent recycled-aggregate route, not the SCM binder route.
    steps = [('Crushing', {}), ('Screening', dict(input_mass_kg=1,output_mass_kg=y))]
    request = dict(functional_unit_kg=1, lca_settings=dict(
        energy_scenario_version=ENERGY_SCENARIO_VERSION,
        input_defaults_version=INPUT_DEFAULTS_VERSION),
        processes=[dict(process_name=name, process_order=i+1,
        parameters=[dict(parameter_code=k,value=v) for k,v in vals.items()]) for i,(name,vals) in enumerate(steps)])
    return characterize_scm(request)


def validate_recipe_transport(config):
    if not isinstance(config, dict) or set(config)-{'enabled','distance_km','moisture_percent','activity_code'}:
        raise ValueError('SCM delivery must contain supported transport settings')
    if not isinstance(config.get('enabled',False),bool):
        raise ValueError('SCM delivery selection must be boolean')
    if config.get('enabled'):
        number(config.get('distance_km'),'SCM delivery distance (km)',positive=True)
        if number(config.get('moisture_percent',0),'SCM cargo moisture (%)') >= 100:
            raise ValueError('SCM cargo moisture must be below 100%')
        code=config.get('activity_code')
        if code is not None and (not isinstance(code,str) or not code):
            raise ValueError('Choose a freight activity for SCM delivery')
    return config


def recipe_transport(payload, item, scm_mass, volume):
    """The current SCM snapshot contains inbound waste transport only."""
    result=dict(included=False,gwp_kg_co2e_m3=0,gwp_kg_co2e_batch=0)
    if item:
        legs = item['snapshot'].get('transport') or []
        if any(not isinstance(leg, dict) or leg.get('key') != 'waste_to_process' for leg in legs):
            raise IncompatibleModelError('Incompatible saved scm material: SCM delivery belongs in the recipe.')
    config=validate_recipe_transport(payload.get('scm_transport', {'enabled': False}))
    if not config.get('enabled',False):
        return result
    if not item or scm_mass<=0:
        raise ValueError('SCM delivery requires a selected SCM item and a positive SCM mass')
    code=config.get('activity_code') or bg.lca_catalogue()['defaults']['transport_code']
    provider=bg.selected_provider('transport',code)
    distance=number(config['distance_km'],'SCM delivery distance',positive=True)
    moisture=number(config.get('moisture_percent',0),'SCM cargo moisture')
    wet_mass=scm_mass/(1-moisture/100)
    tkm=wet_mass/1000*distance
    if not math.isfinite(tkm):
        raise ValueError('SCM delivery demand overflow')
    factor=bg.factors([provider])[provider['code']]
    result.update(included=True,dry_mass_kg=scm_mass,dry_mass_kg_m3=scm_mass/volume,
        wet_mass_kg=wet_mass,wet_mass_kg_m3=wet_mass/volume,ton_km=tkm,ton_km_m3=tkm/volume,
        distance_km=distance,moisture_percent=moisture,provider=provider,factor_kg_co2e_tkm=factor,
        gwp_kg_co2e_batch=tkm*factor,gwp_kg_co2e_m3=tkm/volume*factor)
    return result


def calculate_recipe(payload, get_material):
    if not isinstance(payload, dict):
        raise ValueError('Recipe must be a JSON object')
    kind = payload.get('specimen_class')
    if kind not in ('paste','mortar','concrete','foam_concrete'):
        raise ValueError('Choose paste, mortar, concrete or foam concrete')
    basis = payload.get('basis', DEFAULTS['basis'])
    if basis not in ('per_m3','batch'):
        raise ValueError('Recipe basis must be per_m3 or batch')
    amounts = payload.get('amounts',{})
    if not isinstance(amounts,dict):
        raise ValueError('Ingredient amounts must be an object')
    roles = ('cement','scm','sand','aggregate','recycled_fine','recycled_coarse','water')
    if set(amounts)-set(roles):
        raise ValueError('Unsupported ingredient: '+', '.join(sorted(set(amounts)-set(roles))))
    masses = {k:number(amounts.get(k,0),k+' mass') for k in roles}
    direct_input = payload.get('direct_materials', [])
    if not isinstance(direct_input, list) or len(direct_input) > 30:
        raise ValueError('Direct materials must be a list of at most 30 ingredients')
    direct = []
    used_codes = set()
    for index, entry in enumerate(direct_input, 1):
        if not isinstance(entry, dict) or set(entry) - {'activity_code','mass_kg','category','density_kg_m3'}:
            raise ValueError(f'Direct material {index} has unsupported fields')
        source = bg.recipe_material(entry.get('activity_code'))
        if source['code'] in used_codes:
            raise ValueError('Add each direct ecoinvent activity only once')
        used_codes.add(source['code'])
        category = entry.get('category', 'other')
        if category not in ('binder','aggregate','other'):
            raise ValueError(f'Direct material {index}: choose binder, aggregate or other')
        mass = number(entry.get('mass_kg'), f'Direct material {index} mass', positive=True)
        density = entry.get('density_kg_m3')
        density = number(density, f'Direct material {index} density', positive=True) if density not in (None, '') else None
        direct.append(dict(source=source, category=category, mass_kg=mass, density_kg_m3=density))
    direct_binder = math.fsum(r['mass_kg'] for r in direct if r['category'] == 'binder')
    direct_aggregate = math.fsum(r['mass_kg'] for r in direct if r['category'] == 'aggregate')
    binder_mass = masses['cement'] + masses['scm'] + direct_binder
    if binder_mass <= 0 or masses['water'] <= 0:
        raise ValueError('A binder (cement, saved SCM or direct binder) and recipe water are required')
    if kind == 'paste' and (direct_aggregate or any(masses[k] for k in ('sand','aggregate','recycled_fine','recycled_coarse'))):
        raise ValueError('Paste must not contain fine or coarse aggregate')
    if kind == 'mortar' and any(masses[k] for k in ('aggregate','recycled_coarse')):
        raise ValueError('Mortar must not contain coarse aggregate')
    if kind in ('mortar','concrete') and not (direct_aggregate or any(masses[k] for k in ('sand','aggregate','recycled_fine','recycled_coarse'))):
        raise ValueError('Mortar/concrete needs at least one applicable aggregate fraction')
    item = get_material(payload.get('scm_item_id')) if masses['scm'] else None
    if masses['scm'] and not item:
        raise ValueError('Select a saved SCM material item')
    if item:
        require_current_settings(item['snapshot'].get('pathway', {}).get('lca_settings'),
                                 label='Saved SCM material')
    densities = payload.get('densities',{})
    if not isinstance(densities,dict):
        raise ValueError('Densities must be an object')
    rho = DEFAULT_DENSITIES_KG_PER_M3.copy()
    if item:
        rho['scm']=item['density_kg_m3']
    for k,v in densities.items():
        if k not in roles:
            raise ValueError('Unknown density ingredient: '+k)
        rho[k]=number(v,k+' density',positive=True)
    air = number(payload.get('air_percent', DEFAULTS['air_percent']),'Air content')
    if air >= 100:
        raise ValueError('Air content must be below 100%')
    total_mass=math.fsum([*masses.values(), *(r['mass_kg'] for r in direct)])
    if not math.isfinite(total_mass):
        raise ValueError('Recipe mass overflow')
    volume_mode=payload.get('volume_mode', DEFAULTS['volume_mode'])
    if basis=='per_m3':
        volume=1
        volume_note='User-declared kg per 1 m³; not silently renormalized.'
    elif volume_mode=='measured':
        volume=number(payload.get('measured_volume_m3'),'Measured fresh batch volume',positive=True)
        volume_note='User-supplied fresh batch volume.'
    elif volume_mode=='absolute':
        if any(r['density_kg_m3'] is None for r in direct):
            raise ValueError('Enter particle density for every direct material, or use a measured batch volume')
        volume=math.fsum([*(masses[k]/rho[k] for k in roles if masses[k]),
                          *(r['mass_kg']/r['density_kg_m3'] for r in direct)])/(1-air/100)
        volume_note='Density-based absolute-volume closure; conditional estimate, not measured fresh volume.'
    else:
        raise ValueError('Unknown batch-volume mode')
    if not math.isfinite(volume) or volume<=0:
        raise ValueError('Recipe volume must be positive and finite')
    providers=bg.catalogue()['providers']
    cement_code=payload.get('cement_code')
    if cement_code is not None and not isinstance(cement_code, str):
        raise ValueError('Cement activity code must be a string')
    cement_code=cement_code or providers['cement']['code']
    if masses['cement']:
        allowed={r['code']:r for r in bg.catalogue()['cements']}
        if cement_code not in allowed:
            raise ValueError('Choose a cement activity from the connected catalogue')
        cement=allowed[cement_code]
    else:
        cement=None
    sources={k:providers[k] for k in ('sand','aggregate','water')}
    sources['cement']=cement
    factors=bg.factors([*(v for k,v in sources.items() if masses[k]), *(r['source'] for r in direct)])
    recycled=recycled_inventory(payload.get('recycled_yield_fraction', DEFAULTS['recycled_yield_fraction'])) if masses['recycled_fine']+masses['recycled_coarse'] else None
    delivery=recipe_transport(payload,item,masses['scm'],volume)
    rows=[]
    for k in roles:
        if not masses[k]:
            continue
        if k=='scm':
            factor=item['snapshot']['gwp_kg_co2e_kg']
            source=dict(item_id=item['id'],name=item['name'],snapshot_hash=item['snapshot_hash'],method=item['snapshot']['method'],
                        boundary='SCM production including recorded waste transport; SCM delivery accounted separately in recipe',
                        transport=item['snapshot'].get('transport', []))
            if source['method'] != bg.METHOD:
                raise ValueError('SCM item method differs from recipe LCIA method')
        elif k.startswith('recycled_'):
            factor=recycled['gwp_kg_co2e_kg'];source=dict(name='Framework Crushing → Screening')
        else:
            source=sources[k];factor=factors[source['code']]
        rows.append(dict(ingredient=k,mass_kg=masses[k],mass_kg_m3=masses[k]/volume,
            factor_kg_co2e_kg=factor,gwp_kg_co2e_m3=masses[k]/volume*factor,source=source))
    for index, entry in enumerate(direct, 1):
        source=entry['source'];factor=factors[source['code']];mass=entry['mass_kg']
        rows.append(dict(ingredient='direct',direct_index=index,category=entry['category'],
            density_kg_m3=entry['density_kg_m3'],mass_kg=mass,mass_kg_m3=mass/volume,
            factor_kg_co2e_kg=factor,gwp_kg_co2e_m3=mass/volume*factor,source=source))
    include=payload.get('include_preparation',True)
    if not isinstance(include,bool):
        raise ValueError('Preparation selection must be boolean')
    mode=payload.get('preparation_mode', DEFAULTS['preparation_mode'] if include else 'none')
    if mode=='common':
        mode='mixing'  # Legacy saved recipe input; the inventory and result are unchanged.
    if mode not in ('mixing','foam','none'):
        raise ValueError('Choose a supported mixing preparation inventory')
    if mode=='mixing' and kind=='foam_concrete':
        raise ValueError('Mixing inventory applies to paste, mortar and concrete only')
    if mode=='foam' and kind!='foam_concrete':
        raise ValueError('Foam-concrete mixing is available for foam concrete recipes only')
    if mode=='foam':
        reference_mass=number(payload.get('foam_reference_mass_kg',DEFAULTS['foam_reference_mass_kg']),'Foam mixing reference mass',positive=True)
        machine_conversion=number(payload.get('foam_machine_kg_per_unit',DEFAULTS['foam_machine_kg_per_unit']),'Heavy-machine kg per unit',positive=True)
        electricity=providers['electricity'];machine=providers['machine']
        scores=bg.factors([electricity,machine])
        scale=total_mass/volume/reference_mass
        exchange_rows=[dict(provider=electricity,amount_per_reference=FOAM_ELECTRICITY_KWH,
                            unit='kilowatt hour',amount_per_m3=scale*FOAM_ELECTRICITY_KWH,
                            factor=scores[electricity['code']],gwp_kg_co2e_m3=scale*FOAM_ELECTRICITY_KWH*scores[electricity['code']]),
                       dict(provider=machine,amount_per_reference=FOAM_MACHINE_UNIT,
                            unit='unit',conversion_kg_per_unit=machine_conversion,
                            amount_per_m3=scale*FOAM_MACHINE_UNIT*machine_conversion,
                            characterized_unit='kilogram',factor=scores[machine['code']],
                            gwp_kg_co2e_m3=scale*FOAM_MACHINE_UNIT*machine_conversion*scores[machine['code']])]
        prep_gwp=math.fsum(row['gwp_kg_co2e_m3'] for row in exchange_rows)
        prep=dict(mode='foam',included=True,source='User-supplied foam-concrete mixing inventory; reference mass provisional',
                  reference_mass_kg=reference_mass,reference_mass_status='unverified',
                  machine_conversion_status='inferred conversion, not independently verified',
                  electricity_kwh_m3=exchange_rows[0]['amount_per_m3'],
                  machine_kg_m3=exchange_rows[1]['amount_per_m3'],exchanges=exchange_rows,gwp_kg_co2e_m3=prep_gwp)
    elif mode=='mixing':
        prep={**bg.preparation_gwp(), 'mode':mode, 'included':True}
        prep_gwp=prep['gwp_kg_co2e_m3']
    else:
        prep=dict(mode='none', included=False, gwp_kg_co2e_m3=0,
                  source='Mixing inventory excluded by user')
        prep_gwp=0
    total=math.fsum(r['gwp_kg_co2e_m3'] for r in rows)+prep_gwp+delivery['gwp_kg_co2e_m3']
    if not math.isfinite(total):
        raise ValueError('Recipe GWP overflow')
    strength=payload.get('strength_mpa')
    age=payload.get('strength_age_days',28)
    matched=payload.get('strength_matches_recipe',False)
    if not isinstance(matched,bool):
        raise ValueError('Strength confirmation must be boolean')
    index=None; reason='Enter the composition-matched 28-day compressive strength.'
    if strength not in (None,''):
        strength=number(strength,'Compressive strength',positive=True)
        age=number(age,'Strength age',positive=True)
        if age!=28:
            reason='The paper index requires 28-day strength; another age is not substituted.'
        elif not matched:
            reason='Confirm that strength matches this route, composition, replacement level and specimen class.'
        else:
            index=total/strength;reason='Within-specimen-class screening only; not proof of performance equivalence.'
    reference=None
    reference_code=payload.get('reference_concrete_code')
    if reference_code not in (None, ''):
        if kind!='concrete':
            raise ValueError('A concrete reference can be compared with a concrete recipe only')
        if mode!='mixing':
            raise ValueError('Include the Mixing inventory before comparing with concrete production')
        if item and item['snapshot'].get('background_fingerprint')!=bg.fingerprint():
            raise ValueError('The saved SCM uses a different background snapshot; recalculate it before comparing with the concrete reference')
        if strength is None or age!=28 or not matched:
            raise ValueError('Confirm the current recipe’s measured 28-day strength before comparing concrete')
        source=bg.concrete_reference(reference_code)
        if not math.isclose(strength, source['strength_mpa'], rel_tol=0, abs_tol=1e-6):
            raise ValueError('Choose a concrete production reference with the same MPa value as this recipe')
        reference_gwp=bg.factors([source])[source['code']]
        if not math.isfinite(reference_gwp) or reference_gwp<=0:
            raise bg.BackgroundUnavailable('The selected concrete reference has no positive finite GWP factor')
        difference=reference_gwp-total
        reference=dict(source=source, strength_mpa=source['strength_mpa'],
                       reference_age_days=source['age_days'], current_age_days=age,
                       gwp_kg_co2e_m3=reference_gwp,
                       difference_kg_co2e_m3=difference, reduction_percent=100*difference/reference_gwp,
                       method=bg.METHOD, background_fingerprint=bg.fingerprint(),
                       age_note=('Reference metadata states 28-day compressive strength.'
                                 if source['age_days']==28 else
                                 'Reference test age is not stated; the MPa class match is nominal.'),
                       boundary_note='The reference is an ecoinvent concrete production activity per 1 m³; its upstream boundary may differ from the entered recipe.')
    warnings=['SCM delivery is controlled in this recipe and counted once, separately from SCM production. Recorded waste-to-processing transport stays in the SCM ingredient.',
              'Delivery of other ingredients, unlisted admixtures, curing/use-stage and end-of-life burdens are excluded.',
              'Default densities are conversion assumptions. Replace them with measured values where available.']
    if mode=='foam':
        warnings.append(f'Foam mixing reference mass ({reference_mass:g} kg; default 1 tonne) and heavy-machine conversion ({machine_conversion:g} kg/unit) are provisional; verify against the original inventory before reporting final results.')
    if mode=='none':
        warnings.append('Mixture preparation excluded by user; '+('subtotal includes ingredients and selected SCM delivery.' if delivery['included'] else 'this is a constituent-only subtotal.'))
    if item and item['snapshot'].get('background_fingerprint')!=bg.fingerprint():
        warnings.append('The SCM item retains its saved background snapshot; the current database has changed. Create a new item to recharacterize.')
    absolute=math.fsum([*(masses[k]/rho[k] for k in roles if masses[k]),
                        *(r['mass_kg']/r['density_kg_m3'] for r in direct if r['density_kg_m3'] is not None)])/(1-air/100)
    if basis=='per_m3' and all(r['density_kg_m3'] is not None for r in direct) and abs(absolute-1)>.1:
        warnings.append('Density-based estimated volume differs from the declared 1 m³ by more than 10%; check recipe yield and densities.')
    if basis=='per_m3' and any(r['density_kg_m3'] is None for r in direct):
        warnings.append('Some direct materials have no particle density; density-based 1 m³ yield check was skipped.')
    return dict(ok=True,method=bg.METHOD,specimen_class=kind,basis=basis,
        background_fingerprint=bg.fingerprint(), densities_kg_m3=rho, air_percent=air,
        batch_volume_m3=volume,volume_note=volume_note,fresh_density_kg_m3=total_mass/volume,
        binder_kg_m3=binder_mass/volume,
        water_binder_ratio=masses['water']/binder_mass,
        scm_replacement_fraction=masses['scm']/binder_mass,
        ingredients=rows,scm_transport=delivery,preparation=prep,
        gwp_kg_co2e_m3=total,gwp_kg_co2e_batch=total*volume,
        performance=dict(index_kg_co2e_m3_mpa=index,strength_mpa=strength,age_days=age,note=reason),
        recycled_route=recycled, reference_concrete=reference, warnings=warnings)
