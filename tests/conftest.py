"""Pytest configuration and shared fixtures."""

import json
import tempfile
import shutil
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest


@pytest.fixture
def temp_config():
    """Use a temporary config directory for tests."""
    tmpdir = tempfile.mkdtemp(prefix="neuralclaw_test_")
    config_dir = Path(tmpdir) / "neuralclaw"
    config_dir.mkdir()
    vault_dir = config_dir / "vault"
    vault_dir.mkdir()
    (vault_dir / ".gitignore").write_text("*\n!.gitignore\n")

    info = {
        "tmpdir": tmpdir,
        "config_dir": config_dir,
        "vault_dir": vault_dir,
        "db_path": config_dir / "neuralclaw.db",
        "vault_key_path": config_dir / "vault.key",
    }

    yield info

    # Cleanup
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def fresh_db(temp_config):
    """Initialize a fresh database for testing."""
    # Patch appdirs BEFORE any neuralclaw module is imported
    with patch("appdirs.user_config_dir", lambda x=None: temp_config["tmpdir"]):
        # Clear any previously imported neuralclaw modules
        import sys
        for mod in list(sys.modules.keys()):
            if "neuralclaw" in mod:
                sys.modules.pop(mod, None)

        from neuralclaw.db.connection import init_db
        init_db()
        yield


@pytest.fixture
def sample_project(fresh_db):
    """Create a sample project for tests."""
    from neuralclaw.core.projects import create_project
    return create_project("sample-project", "Sample project for testing")


@pytest.fixture
def vaultInitialized(fresh_db, temp_config):
    """Initialize vault for tests that need it.

    Note: vault.key is stored at config/vault.key (not in vault/),
    so we verify it by checking via the vault module functions.
    """
    from neuralclaw.core.vault import init_vault, get_vault_key_path
    init_vault()
    # Verify using the actual vault module path
    assert get_vault_key_path().exists(), f"vault.key not at expected path: {get_vault_key_path()}"
    return True
