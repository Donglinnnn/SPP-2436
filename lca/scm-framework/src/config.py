import os
import tomllib
from functools import lru_cache
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
DB_PATH = DATA_DIR / "scm_projects.sqlite3"

FRONTEND_DIR = ROOT_DIR / "frontend"
FRONTEND_STATIC_DIR = FRONTEND_DIR / "static"
FRONTEND_TEMPLATE_DIR = FRONTEND_DIR / "templates"

FLASK_HOST = "127.0.0.1"
FLASK_PORT = 5050


@lru_cache(maxsize=1)
def local_settings() -> dict:
    """Optional, untracked settings for this computer only."""
    path = ROOT_DIR / "local_config.toml"
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except FileNotFoundError:
        return {}


def background_setting(env_name: str, local_name: str) -> str | None:
    """Environment overrides the optional local configuration file."""
    value = os.environ.get(env_name)
    if value is not None:
        return value or None
    background = local_settings().get("background", {})
    value = background.get(local_name) if isinstance(background, dict) else None
    return value if isinstance(value, str) and value.strip() else None
