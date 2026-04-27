"""Vault - Encrypted secret storage."""

import hashlib
import secrets
import json
from pathlib import Path
from typing import Generator

from cryptography.fernet import Fernet, InvalidToken

from neuralclaw.db.connection import get_vault_dir, get_vault_key_path, get_connection


def _get_fernet() -> Fernet:
    """Get Fernet instance with current key."""
    key_path = get_vault_key_path()
    if not key_path.exists():
        raise RuntimeError(
            "Vault key not found. Run 'neuralclaw init' first."
        )
    key = key_path.read_text().strip()
    return Fernet(key.encode())


def generate_key() -> str:
    """Generate a new Fernet key."""
    return Fernet.generate_key().decode()


def init_vault() -> None:
    """Initialize the vault with a new encryption key."""
    key_path = get_vault_key_path()
    vault_dir = get_vault_dir()

    # Generate and save key if it doesn't exist
    if not key_path.exists():
        key = generate_key()
        key_path.write_text(key)
        # Secure permissions
        key_path.chmod(0o600)

    # Initialize vault DB
    vault_db = vault_dir / "vault.db"
    conn = _get_vault_conn(vault_db)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS vault_entries (
            id TEXT PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            encrypted_value TEXT NOT NULL,
            value_hash TEXT,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        );
    """)
    conn.commit()
    conn.close()


def _get_vault_conn(db_path: Path):
    """Get a connection to the vault database."""
    import sqlite3
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _encrypt_value(value: str) -> str:
    """Encrypt a value using Fernet."""
    f = _get_fernet()
    return f.encrypt(value.encode()).decode()


def _decrypt_value(encrypted: str) -> str:
    """Decrypt a value using Fernet."""
    f = _get_fernet()
    return f.decrypt(encrypted.encode()).decode()


def vault_set(name: str, value: str) -> None:
    """Store a secret in the vault."""
    import uuid
    vault_dir = get_vault_dir()
    vault_db = vault_dir / "vault.db"

    if not vault_db.exists():
        init_vault()

    encrypted = _encrypt_value(value)
    value_hash = hashlib.sha256(value.encode()).hexdigest()
    now = __import__("time").time()

    conn = _get_vault_conn(vault_db)
    # Upsert
    conn.execute("""
        INSERT INTO vault_entries (id, name, encrypted_value, value_hash, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(name) DO UPDATE SET
            encrypted_value = excluded.encrypted_value,
            value_hash = excluded.value_hash,
            updated_at = excluded.updated_at
    """, (str(uuid.uuid4()), name.upper(), encrypted, value_hash, now, now))
    conn.commit()
    conn.close()


def vault_get(name: str) -> str | None:
    """Retrieve a secret from the vault. Returns None if not found."""
    vault_dir = get_vault_dir()
    vault_db = vault_dir / "vault.db"

    if not vault_db.exists():
        return None

    conn = _get_vault_conn(vault_db)
    row = conn.execute(
        "SELECT encrypted_value FROM vault_entries WHERE name = ?",
        (name.upper(),)
    ).fetchone()
    conn.close()

    if not row:
        return None

    return _decrypt_value(row["encrypted_value"])


def vault_list() -> list[str]:
    """List all secret names (no values)."""
    vault_dir = get_vault_dir()
    vault_db = vault_dir / "vault.db"

    if not vault_db.exists():
        return []

    conn = _get_vault_conn(vault_db)
    rows = conn.execute(
        "SELECT name FROM vault_entries ORDER BY name"
    ).fetchall()
    conn.close()

    return [row["name"] for row in rows]


def vault_delete(name: str) -> bool:
    """Delete a secret. Returns True if deleted."""
    vault_dir = get_vault_dir()
    vault_db = vault_dir / "vault.db"

    if not vault_db.exists():
        return False

    conn = _get_vault_conn(vault_db)
    cur = conn.execute(
        "DELETE FROM vault_entries WHERE name = ?",
        (name.upper(),)
    )
    conn.commit()
    deleted = cur.rowcount > 0
    conn.close()
    return deleted


def vault_exists() -> bool:
    """Check if vault is initialized."""
    return get_vault_key_path().exists()
