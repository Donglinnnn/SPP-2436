"""Installation-time, read-only connection check for a user's Brightway project."""

import sys


def main() -> int:
    try:
        from src.recipes import background as bg
    except ValueError as exc:
        print(f'FAIL Invalid local background configuration: {exc}', file=sys.stderr)
        return 1
    try:
        project = bg.configured_project()
        print(f'OK   Brightway project: {project}')
        print(f'OK   worker Python: {bg.PYTHON}')
        catalogue = bg.catalogue()
        print(f'OK   database and {len(catalogue["providers"])} configured providers: {bg.DATABASE}')
        factories = [catalogue['providers'][key] for key in ('thermal_factory', 'carbonation_factory')]
        if any(provider['unit'] != 'unit' for provider in factories):
            raise bg.BackgroundUnavailable('Thermal activation and carbonation factories must use unit-based providers.')
        print('OK   thermal activation and carbonation factory providers: unit basis')
        lca = bg.lca_catalogue()
        print(f'OK   paired energy scenario and freight catalogue: {len(lca["energy_scenarios"])} / {len(lca["transport"])}')
        from src.recipes.co2_sources import SOURCES
        for source in SOURCES.values():
            for name, location, _, unit in source['entries']:
                bg.exact_activity(name, location, unit)
            for name, categories, _, unit in source['elementary']:
                bg.exact_elementary(name, categories, unit)
        print(f'OK   authored CO2 supply inventories: {len(SOURCES)} exact source definitions')
        packages = bg.resolved_packages()
        print(f'OK   LCIA method and {len(packages)} processed packages: {" / ".join(bg.METHOD)}')
        electricity = catalogue['providers']['electricity']
        checked_providers = [electricity, *factories]
        result = bg.run_worker(checked_providers)
        if any(provider['code'] not in result['scores'] for provider in checked_providers):
            raise bg.BackgroundUnavailable('Brightway did not return all requested electricity and factory scores.')
        print('OK   isolated LCA calculation: finite score and solver residual checked')
    except (bg.BackgroundUnavailable, ValueError, KeyError) as exc:
        print(f'FAIL {exc}', file=sys.stderr)
        return 1
    try:
        bg.preparation_gwp()
        print('OK   optional mixing inventory is available')
    except bg.BackgroundUnavailable:
        print('INFO optional mixing inventory is unavailable; choose no mixing inventory or foam mixing')
    print('READY Local LCA connection is usable. No source database was modified.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
