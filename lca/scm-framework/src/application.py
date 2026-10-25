from flask import Flask, render_template

from src.config import FRONTEND_STATIC_DIR, FRONTEND_TEMPLATE_DIR
from src.routes import register_api_blueprints


def create_app() -> Flask:
    app = Flask(
        __name__,
        static_folder=str(FRONTEND_STATIC_DIR),
        template_folder=str(FRONTEND_TEMPLATE_DIR),
    )

    @app.get("/")
    def index():
        return render_template("workspace.html")

    @app.get("/recipes", strict_slashes=False)
    def recipes_index():
        return render_template("recipes.html")

    register_api_blueprints(app)
    return app
