"""Database connection and initialization."""

import os
import sqlite3
from pathlib import Path
from contextlib import contextmanager
from typing import Generator

import appdirs

DB_NAME = "neuralclaw.db"
SCHEMA_FILE = Path(__file__).parent / "schema.sql"


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
    # Enable FTS5
    conn.execute("PRAGMA fts5 = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


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


def db_exists() -> bool:
    """Check if database exists."""
    return get_db_path().exists()


def get_schema_version() -> str | None:
    """Get the current schema version."""
    if not db_exists():
        return None
    with get_connection() as conn:
        row = conn.execute(
            "SELECT version FROM schema_version ORDER BY applied_at DESC LIMIT 1"
        ).fetchone()
        return row["version"] if row else None
