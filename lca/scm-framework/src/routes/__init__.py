from flask import Flask

from src.routes.health_routes import register_health_routes
from src.routes.project_routes import register_project_routes
from src.routes.calculation_routes import register_calculation_routes
from src.routes.recipe_routes import register_recipe_routes


def register_api_blueprints(app: Flask) -> None:
    from flask import Blueprint

    api_v1 = Blueprint("api_v1", __name__, url_prefix="/api/v1")
    api_alias = Blueprint("api", __name__, url_prefix="/api")

    register_health_routes(api_v1)
    register_health_routes(api_alias)
    register_project_routes(api_v1)
    register_project_routes(api_alias)
    register_calculation_routes(api_v1)
    register_calculation_routes(api_alias)
    register_recipe_routes(api_v1)

    app.register_blueprint(api_v1)
    app.register_blueprint(api_alias)
