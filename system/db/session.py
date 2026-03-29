from __future__ import annotations

import os
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from system.db.base import Base
from system.db.config import REPO_ROOT, get_database_url
import system.db.models  # noqa: F401


_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None
_active_database_url: str | None = None
_bootstrap_complete = False
_bootstrap_lock = threading.RLock()
APP_ENV_ENV = "DISCOVERY_APP_ENV"
AUTO_APPLY_MIGRATIONS_ENV = "DISCOVERY_AUTO_APPLY_MIGRATIONS"
ALLOW_SCHEMA_CREATE_ENV = "DISCOVERY_ALLOW_SCHEMA_CREATE"
PRODUCTION_APP_ENVS = {"production", "staging"}


def _env_flag(name: str, default: bool) -> bool:
    value = os.getenv(name, "").strip().lower()
    if not value:
        return default
    return value in {"1", "true", "yes", "on"}


def _app_env() -> str:
    return os.getenv(APP_ENV_ENV, "development").strip().lower() or "development"


def _should_auto_apply_migrations() -> bool:
    return _env_flag(AUTO_APPLY_MIGRATIONS_ENV, default=_app_env() not in PRODUCTION_APP_ENVS)


def _allow_schema_create_fallback() -> bool:
    return _env_flag(ALLOW_SCHEMA_CREATE_ENV, default=_app_env() not in PRODUCTION_APP_ENVS)


def _engine_kwargs(database_url: str) -> dict:
    kwargs = {"future": True, "pool_pre_ping": True}
    if database_url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    return kwargs


def get_engine() -> Engine:
    global _engine, _session_factory, _active_database_url, _bootstrap_complete

    database_url = get_database_url()
    with _bootstrap_lock:
        if _engine is None or _active_database_url != database_url:
            _engine = create_engine(database_url, **_engine_kwargs(database_url))
            _session_factory = sessionmaker(bind=_engine, autoflush=False, autocommit=False, expire_on_commit=False, future=True)
            _active_database_url = database_url
            _bootstrap_complete = False
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    engine = get_engine()
    assert _session_factory is not None
    return _session_factory


def _run_alembic_upgrade() -> bool:
    try:
        from alembic import command
        from alembic.config import Config
    except ImportError:
        return False

    alembic_ini = REPO_ROOT / "alembic.ini"
    script_location = REPO_ROOT / "alembic"
    if not alembic_ini.exists() or not script_location.exists():
        return False

    config = Config(str(alembic_ini))
    config.set_main_option("script_location", str(script_location))
    config.set_main_option("sqlalchemy.url", get_database_url())
    command.upgrade(config, "head")
    return True


def ensure_database_ready() -> None:
    global _bootstrap_complete

    engine = get_engine()
    with _bootstrap_lock:
        if _bootstrap_complete:
            return
        database_url = get_database_url()
        if database_url.startswith("sqlite:///"):
            db_path = Path(database_url.replace("sqlite:///", "", 1))
            db_path.parent.mkdir(parents=True, exist_ok=True)
        if _should_auto_apply_migrations():
            migrated = _run_alembic_upgrade()
            if not migrated:
                if _allow_schema_create_fallback():
                    Base.metadata.create_all(bind=engine)
                else:
                    raise RuntimeError("Database migrations must be applied before the app starts. Run `alembic upgrade head`.")
        elif _allow_schema_create_fallback():
            Base.metadata.create_all(bind=engine)
        _bootstrap_complete = True


@contextmanager
def session_scope() -> Iterator[Session]:
    ensure_database_ready()
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def reset_database_state(database_url: str | None = None) -> None:
    global _engine, _session_factory, _active_database_url, _bootstrap_complete

    with _bootstrap_lock:
        if _engine is not None:
            _engine.dispose()
        _engine = None
        _session_factory = None
        _active_database_url = None
        _bootstrap_complete = False
        if database_url is None:
            os.environ.pop("DISCOVERY_DATABASE_URL", None)
        else:
            os.environ["DISCOVERY_DATABASE_URL"] = database_url
