"""Pytest configuration and shared fixtures with debugging."""

import json
import tempfile
import shutil
from pathlib import Path

import pytest


@pytest.fixture
def temp_config():
    """Use a temporary config directory for tests (function-scoped, unique per test)."""
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

    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def fresh_db(temp_config):
    """Initialize a fresh database for testing.

    Patches appdirs.user_config_dir (the root cause) to use the temp config
    directory, then clears any neuralclaw modules and calls init_db().
    """
    import sys
    import appdirs

    # Clear all neuralclaw modules so they re-import with patched config
    for mod in list(sys.modules.keys()):
        if "neuralclaw" in mod:
            sys.modules.pop(mod, None)

    orig_user_config_dir = appdirs.user_config_dir
    appdirs.user_config_dir = lambda x=None: str(temp_config["config_dir"])

    try:
        from neuralclaw.db.connection import init_db
        init_db()
        yield
    finally:
        appdirs.user_config_dir = orig_user_config_dir


@pytest.fixture
def sample_project(fresh_db):
    """Create a sample project for tests."""
    from neuralclaw.core.projects import create_project
    return create_project("sample-project", "Sample project for testing")


@pytest.fixture
def vaultInitialized(fresh_db, temp_config):
    """Initialize vault for tests that need it."""
    from neuralclaw.core.vault import init_vault
    init_vault()
    return True
