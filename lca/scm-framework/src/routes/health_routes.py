from flask import Blueprint, jsonify

from src.config import DB_PATH


def register_health_routes(blueprint: Blueprint) -> None:
    @blueprint.get("/health")
    def health():
        return jsonify({"ok": True, "database": str(DB_PATH), "service": "scm-project-service"})
