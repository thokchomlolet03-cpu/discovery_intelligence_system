from __future__ import annotations

import os
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
DEFAULT_DATABASE_PATH = DATA_DIR / "discovery_control_plane.db"
DATABASE_URL_ENV = "DISCOVERY_DATABASE_URL"


def default_database_url() -> str:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{DEFAULT_DATABASE_PATH}"


def get_database_url() -> str:
    configured = os.getenv(DATABASE_URL_ENV, "").strip()
    return configured or default_database_url()
