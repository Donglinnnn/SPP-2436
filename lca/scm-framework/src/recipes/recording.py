"""Attach actual LCIA provider choices to the foreground A–B–C record.

The inputs here are the provider and quantity records already used by the
calculation. This module neither accesses a background database nor evaluates
LCIA factors. Public exports contain provider identities, not background scores.
"""
from copy import deepcopy

from src.calculation.units import KWH_TO_MJ
from .electricity_scenarios import DELIVERY_CODES, SCENARIOS


PROVIDER_FIELDS = (
    'code', 'database', 'name', 'location', 'unit', 'reference_product',
    'scenario', 'label', 'source',
)


def provider_identity(provider):
    """Keep stable, shareable identities; omit local integer IDs and scores."""
    return {key: deepcopy(provider[key]) for key in PROVIDER_FIELDS if key in provider}


def _electricity_components(provider):
    scenario = provider.get('scenario')
    if scenario != 'E1' or provider.get('code') != 'paper-E1':
        return []
    definition = SCENARIOS[scenario]
    # The characterization code verifies these identities before using the
    # derived supply. Quantities are not reconstructed from a scalar factor.
    return [dict(role='generation', database='ecoinvent-3.12-cutoff',
                 code=definition['generation_code'],
                 name=definition['generation_name'], location='DE',
                 unit='kilowatt hour'),
            *[dict(role='delivery_chain', database='ecoinvent-3.12-cutoff',
                   code=code, name=name, location='DE',
                   unit='kilowatt hour') for code, name in DELIVERY_CODES.items()]]


def finalize_lcia_recording(records, *, settings, processes, transport,
                            source_components, electricity_source, heat_source, method):
    """Resolve C from a successful SCM LCIA run without changing A or B.

``processes``, ``transport`` and ``source_components`` are the actual records
from ``characterize_scm`` on its fixed 1 kg dry SCM basis. Links are converted
to the functional unit in ``records`` and retain this conversion explicitly.
CO2 source components have their own declared 1 kg external-CO2 basis.
Source-inventory references are relative to the same resolution object, so the
record remains valid when attached beneath ``C.lcia_resolution``.
"""
    recorded = deepcopy(records)
    stage = recorded['C']
    fu = recorded['route']['functional_unit_kg']
    stage['functional_unit_kg'] = fu
    stage['basis'] = 'per_kg_dry_SCM' if fu == 1 else 'requested_final_dry_product'
    stage['scenario_settings'] = {
        key: deepcopy(value) for key, value in settings.items()
    }
    stage['lcia_method'] = list(method)
    stage['energy_supply'] = {
        'scenario': settings.get('electricity_scenario', 'E0'),
        'scenario_definition_version': settings.get('energy_scenario_version'),
        'equipment_electricity': provider_identity(electricity_source),
        'process_heat': provider_identity(heat_source),
        'heat_conversion': {'from_unit': 'kilowatt hour', 'to_unit': 'megajoule', 'multiplier': KWH_TO_MJ},
    }
    stage['lcia_status'] = 'calculated'
    stage['provider_resolution_basis'] = 'requested_final_dry_product'
    stage['provider_resolution_source_basis'] = 'per_1_kg_dry_SCM'
    stage['provider_resolution_scaling_factor'] = fu
    stage['provider_links'] = []
    links = stage['provider_links']
    exchange_ids = {row['exchange_id'] for row in stage['exchanges']}
    source_key = settings.get('co2_source')
    stage['co2_supply_inventory'] = {
        'source': source_key,
        'basis': 'per_1_kg_external_makeup_CO2',
        'status': 'resolved_authored_inventory' if source_key else 'not_applicable',
        'exchanges': [dict(
            component_id=f'co2-supply:{index}', exchange_type=row['kind'],
            quantity=row['amount'], unit=row['unit'],
            provider=provider_identity(row['provider']))
            for index, row in enumerate(source_components, start=1)],
    }
    for process in processes:
        for row in process['contributions']:
            flow = row['flow']
            exchange_id = f"op-{process['process_order']}:{flow}"
            # The LCIA function emits zero CO2 bookkeeping terms even for
            # operations that do not generate them. Do not invent A/B exchanges.
            if exchange_id not in exchange_ids:
                continue
            link = dict(exchange_id=exchange_id, flow_key=flow,
                        quantity=row['amount'] * fu, unit=row['unit'],
                        quantity_basis='allocated_requested_final_dry_product',
                        origin='actual_lcia_calculation')
            if flow in ('co2_emitted_kg', 'co2_stored_kg'):
                link.update(
                    status='explicit_CO2_balance_convention', provider=None,
                    role='direct_emission' if flow == 'co2_emitted_kg' else 'retained_CO2',
                    convention=('Released CO2 contributes positively to the paper balance.'
                                if flow == 'co2_emitted_kg' else
                                'Retained CO2 contributes negatively to the paper balance.'),
                    note='No background elementary-flow identity is resolved for this term.')
            elif flow == 'co2_makeup_kg':
                link.update(
                    status=stage['co2_supply_inventory']['status'],
                    provider=provider_identity(row.get('provider') or {}),
                    source_inventory='co2_supply_inventory',
                    source_inventory_scope='same_resolution', source=source_key)
            else:
                provider = row['provider']
                derived = provider.get('code') == 'paper-E1'
                link.update(status='resolved_derived_supply' if derived else 'resolved_database_activity',
                            provider=provider_identity(provider))
                if derived:
                    link['component_identities'] = _electricity_components(electricity_source)
                    link['note'] = ('Derived delivered-electricity supply, not a single '
                                    'database activity; component quantities are not expanded here.')
                if flow == 'heat_kwh':
                    link['foreground_quantity'] = row['amount'] * fu / KWH_TO_MJ
                    link['foreground_unit'] = 'kilowatt hour'
                    link['conversion_factor'] = KWH_TO_MJ
                    link['mapping_note'] = 'Foreground process-heat kWh converted to market MJ by ×3.6.'
                if flow == 'wastewater_treatment_kg':
                    link['mapping_note'] = ('Foreground kg converted to cubic metres by 0.001; '
                                            'negative demand follows the treatment reference product.')
            links.append(link)
    for leg in transport:
        exchange_id = f"scenario:transport:{leg['key']}"
        stage['exchanges'].append(dict(
            exchange_id=exchange_id, operation_id='scenario:transport',
            process_name=leg['label'], process_order=None,
            flow_key=leg['key'], flow_name=leg['label'], unit='ton kilometer',
            quantity=leg['ton_km'] * fu,
            allocated_quantity=leg['allocated_ton_km'] * fu,
            exchange_type='technosphere', generation_layer=None,
            role='transport', alias_of=None,
            distance_km=leg['distance_km'], moisture_percent=leg['moisture_percent'],
            origin='actual_lcia_scenario',
            generation_note='Wet cargo tonnes multiplied by the selected one-way distance.'))
        links.append(dict(
            exchange_id=exchange_id, flow_key=leg['key'],
            quantity=leg['allocated_ton_km'] * fu, unit='ton kilometer',
            quantity_basis='allocated_requested_final_dry_product',
            origin='actual_lcia_calculation', status='resolved_database_activity',
            provider=provider_identity(leg['provider'])))
    stage['status'] = 'lcia_evaluated_with_explicit_provider_resolution'
    stage['resolution_note'] = (
        'Links record the suppliers, authored CO2-supply inventories and balance '
        'conventions used by this run. Physical-only flows and aliases remain '
        'uncharacterized. No background unit scores or LCIA factors are exported.')
    return recorded
