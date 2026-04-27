"""Database module."""

from neuralclaw.db.connection import (
    get_connection,
    get_db_path,
    get_config_dir,
    get_vault_dir,
    get_vault_key_path,
    init_db,
    db_exists,
    get_schema_version,
)

__all__ = [
    "get_connection",
    "get_db_path",
    "get_config_dir",
    "get_vault_dir",
    "get_vault_key_path",
    "init_db",
    "db_exists",
    "get_schema_version",
]
