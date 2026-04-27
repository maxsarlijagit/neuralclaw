"""Pytest configuration and shared fixtures."""

import json
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_config(monkeypatch):
    """Use a temporary config directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir) / "neuralclaw"
        config_dir.mkdir()
        vault_dir = config_dir / "vault"
        vault_dir.mkdir()
        (vault_dir / ".gitignore").write_text("*\n!.gitignore\n")

        # Patch appdirs to return our temp dir
        import neuralclaw.db.connection as conn_module
        monkeypatch.setattr("neuralclaw.db.connection.appdirs.user_config_dir", lambda x: tmpdir)
        monkeypatch.setattr("neuralclaw.logging.appdirs.user_log_dir", lambda x: tmpdir)

        yield {
            "config_dir": config_dir,
            "vault_dir": vault_dir,
            "db_path": config_dir / "neuralclaw.db",
            "vault_key_path": config_dir / "vault.key",
        }


@pytest.fixture
def fresh_db(temp_config):
    """Initialize a fresh database for testing."""
    from neuralclaw.db.connection import init_db
    init_db()
    yield
    # Cleanup handled by temp_config teardown


@pytest.fixture
def sample_project(fresh_db):
    """Create a sample project for tests."""
    from neuralclaw.core.projects import create_project
    return create_project("sample-project", "Sample project for testing")


@pytest.fixture
def vaultInitialized(fresh_db):
    """Initialize vault for tests that need it."""
    from neuralclaw.core.vault import init_vault
    init_vault()
    return True
