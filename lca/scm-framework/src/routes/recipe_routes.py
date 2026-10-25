from functools import wraps

from flask import jsonify, request
from src.recipes import background, service
from src.recipes.calculation import calculate_scm_lca
from src.recipes.settings import recipe_input_defaults
from src.recipes.supporting_data.mixing import FOAM_ELECTRICITY_KWH, FOAM_MACHINE_UNIT


def recipe_endpoint(fn):
    @wraps(fn)
    def run(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except background.BackgroundUnavailable as exc:
            return jsonify(ok=False, error=str(exc)), 503
        except (ValueError, OverflowError) as exc:
            return jsonify(ok=False, error=str(exc)), 422
    return run


def body():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise ValueError('A JSON object is required')
    return payload


def register_recipe_routes(bp):
    @bp.get('/lca-schema')
    @recipe_endpoint
    def lca_schema():
        return jsonify(background.lca_catalogue())

    @bp.post('/lca/calculate')
    @recipe_endpoint
    def lca_calculate():
        result = calculate_scm_lca(body())
        return jsonify(result), 200 if result['ok'] else 422

    @bp.get('/scm-history')
    @recipe_endpoint
    def scm_history():
        return jsonify(service.scm_history())

    @bp.post('/scm-items/from-project/<int:project_id>')
    @recipe_endpoint
    def scm_item_from_project(project_id):
        return jsonify(service.create_material_from_project(project_id, body())), 201

    @bp.get('/recipe-schema')
    @recipe_endpoint
    def recipe_schema():
        return jsonify(**background.catalogue(), preparation=background.preparation_status(),
            background_fingerprint=background.fingerprint(),
            concrete_references=background.concrete_references(),
            freight=background.lca_catalogue()['transport'],default_freight_code=background.lca_catalogue()['defaults']['transport_code'],
            **recipe_input_defaults(),
            foam_inventory=dict(electricity_kwh=FOAM_ELECTRICITY_KWH, machine_unit=FOAM_MACHINE_UNIT),
            boundary='GWP100 screening only. Saved SCM and/or directly selected kilogram-based ecoinvent markets enter the recipe. Recipe owns SCM delivery, counted once; other ingredient delivery, unlisted admixtures, curing/use stage and end of life excluded.',
            performance='GWP per m³ / composition-matched 28-day compressive strength; compare within the same specimen class only.')

    @bp.get('/recipe-materials')
    @recipe_endpoint
    def recipe_materials():
        return jsonify(items=background.search_recipe_materials(request.args.get('q', '')))

    @bp.get('/scm-items')
    @recipe_endpoint
    def scm_items():
        return jsonify(items=service.list_materials())

    @bp.post('/scm-items')
    @recipe_endpoint
    def scm_item_create():
        return jsonify(service.create_material(body())), 201

    @bp.get('/scm-items/<item_id>')
    @recipe_endpoint
    def scm_item_get(item_id):
        record = service.get_material(item_id)
        return (jsonify(record), 200) if record else (jsonify(ok=False, error='SCM item not found'), 404)

    @bp.post('/recipes/calculate')
    @recipe_endpoint
    def recipe_calculate():
        return jsonify(service.calculate(body()))

    @bp.get('/recipes')
    @recipe_endpoint
    def recipes_list():
        return jsonify(items=service.list_recipes())

    @bp.post('/recipes')
    @recipe_endpoint
    def recipe_create():
        return jsonify(service.create_recipe(body())), 201

    @bp.get('/recipes/<recipe_id>')
    @recipe_endpoint
    def recipe_get(recipe_id):
        record = service.get_recipe(recipe_id)
        return (jsonify(record), 200) if record else (jsonify(ok=False, error='Recipe not found'), 404)
