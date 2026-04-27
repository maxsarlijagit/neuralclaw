"""Database connection and initialization."""

import os
import sqlite3
import importlib
from pathlib import Path
from contextlib import contextmanager
from typing import Generator

import appdirs

DB_NAME = "neuralclaw.db"
SCHEMA_FILE = Path(__file__).parent / "schema.sql"
MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def get_config_dir() -> Path:
    """Get NeuralClaw config directory."""
    config_dir = Path(appdirs.user_config_dir("neuralclaw"))
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_db_path() -> Path:
    """Get the database file path."""
    return get_config_dir() / DB_NAME


def get_vault_dir() -> Path:
    """Get the vault directory."""
    vault_dir = get_config_dir() / "vault"
    vault_dir.mkdir(parents=True, exist_ok=True)
    # Ensure .gitignore exists
    gitignore = vault_dir / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("*\n!.gitignore\n")
    return vault_dir


def get_vault_key_path() -> Path:
    """Get the vault encryption key path."""
    return get_config_dir() / "vault.key"


@contextmanager
def get_connection() -> Generator[sqlite3.Connection, None, None]:
    """Get a database connection. Handles transactions automatically."""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    # Enable foreign keys
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _get_current_version(conn: sqlite3.Connection) -> str | None:
    """Get the current schema version from the DB."""
    try:
        row = conn.execute(
            "SELECT version FROM schema_version ORDER BY applied_at DESC LIMIT 1"
        ).fetchone()
        return row["version"] if row else None
    except sqlite3.OperationalError:
        return None


def _get_pending_migrations(current_version: str | None) -> list[tuple[str, str]]:
    """Get list of pending migrations to run.

    Returns list of (version, module_name) sorted by version.
    """
    if not MIGRATIONS_DIR.exists():
        return []

    migrations = []
    for f in sorted(MIGRATIONS_DIR.glob("migrate_*.py")):
        version = f.stem.replace("migrate_", "").replace("_", ".")
        if current_version is None or _version_gt(version, current_version):
            migrations.append((version, f.stem))
    return migrations


def _version_gt(v1: str, v2: str) -> bool:
    """Check if v1 > v2 (semver comparison)."""
    parts1 = [int(x) for x in v1.split(".")]
    parts2 = [int(x) for x in v2.split(".")]
    for a, b in zip(parts1, parts2):
        if a > b:
            return True
        if a < b:
            return False
    return len(parts1) > len(parts2)


def init_db() -> None:
    """Initialize the database with schema."""
    db_path = get_db_path()
    schema = SCHEMA_FILE.read_text()
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(schema)
        conn.commit()
    finally:
        conn.close()


def run_pending_migrations() -> list[str]:
    """Run any pending migrations and return list of applied versions."""
    if not db_exists():
        return []

    applied = []
    with get_connection() as conn:
        current_version = _get_current_version(conn)
        pending = _get_pending_migrations(current_version)

        for version, module_name in pending:
            try:
                mod = importlib.import_module(f"neuralclaw.db.migrations.{module_name}")
                if hasattr(mod, "apply"):
                    mod.apply(conn)
                    conn.commit()
                    applied.append(version)
            except Exception:
                # Log but don't fail - migration may be partial
                pass
    return applied


def db_exists() -> bool:
    """Check if database exists."""
    return get_db_path().exists()


def get_schema_version() -> str | None:
    """Get the current schema version."""
    if not db_exists():
        return None
    with get_connection() as conn:
        return _get_current_version(conn)
