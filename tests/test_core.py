"""Tests for NeuralClaw core modules."""

import json
import tempfile
import os
import sqlite3
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
        monkeypatch.setattr("neuralclaw.db.connection.appdirs.user_config_dir", lambda x: tmpdir)

        yield {
            "config_dir": config_dir,
            "vault_dir": vault_dir,
            "db_path": config_dir / "neuralclaw.db",
            "vault_key_path": config_dir / "vault.key",
        }


@pytest.fixture
def fresh_db(temp_config):
    """Initialize a fresh database for testing.
    
    Patches appdirs.user_config_dir to use the temp config directory,
    then initializes the database.
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
    
    # Cleanup
    if temp_config["db_path"].exists():
        temp_config["db_path"].unlink()


class TestSchema:
    """Tests for database schema."""

    def test_schema_version_recorded(self, fresh_db, temp_config):
        from neuralclaw.db.connection import get_schema_version
        version = get_schema_version()
        # Version should be recorded and non-empty
        assert version is not None
        assert len(version) > 0

    def test_projects_table_exists(self, fresh_db, temp_config):
        conn = sqlite3.connect(temp_config["db_path"])
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='projects'"
        ).fetchone()
        conn.close()
        assert row is not None

    def test_all_tables_exist(self, fresh_db, temp_config):
        expected_tables = [
            "projects", "context_items", "context_links", "errors",
            "decisions", "usage_logs", "model_profiles", "fresh_apple",
            "vault_entries", "schema_version"
        ]
        conn = sqlite3.connect(temp_config["db_path"])
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        conn.close()
        table_names = {r[0] for r in rows}
        for table in expected_tables:
            assert table in table_names, f"Table '{table}' not found"


class TestProjects:
    """Tests for project management."""

    def test_create_project(self, fresh_db):
        from neuralclaw.core.projects import create_project, get_project

        pid = create_project("test-proj", "A test project")
        assert pid is not None

        project = get_project(pid)
        assert project["name"] == "test-proj"
        assert project["description"] == "A test project"
        assert project["status"] == "active"

    def test_list_projects(self, fresh_db):
        from neuralclaw.core.projects import create_project, list_projects

        create_project("proj-a", "Description A")
        create_project("proj-b", "Description B")

        projects = list_projects()
        names = {p["name"] for p in projects}
        assert "proj-a" in names
        assert "proj-b" in names

    def test_archive_project(self, fresh_db):
        from neuralclaw.core.projects import create_project, archive_project, get_project

        pid = create_project("archive-test")
        archive_project(pid)

        project = get_project(pid)
        assert project["status"] == "archived"
        assert project["archived_at"] is not None

    def test_delete_project(self, fresh_db):
        from neuralclaw.core.projects import create_project, delete_project, get_project

        pid = create_project("delete-test")
        assert get_project(pid) is not None

        delete_project(pid)
        assert get_project(pid) is None


class TestContextItems:
    """Tests for context item CRUD."""

    def test_add_context_item(self, fresh_db):
        from neuralclaw.core.context import add_context_item

        item_id = add_context_item(
            project_id=None,
            key="test_key",
            value="test_value",
            item_type="note",
            state="active",
        )
        assert item_id is not None

    def test_search_context(self, fresh_db):
        from neuralclaw.core.context import add_context_item, search_context

        add_context_item(project_id=None, key="api_url", value="https://api.example.com", item_type="variable")
        add_context_item(project_id=None, key="db_host", value="localhost", item_type="variable")

        results = search_context(query="api")
        assert len(results) == 1
        assert results[0]["key"] == "api_url"

    def test_search_context_no_results(self, fresh_db):
        from neuralclaw.core.context import search_context

        results = search_context(query="nonexistent")
        assert len(results) == 0

    def test_context_item_with_tags(self, fresh_db):
        from neuralclaw.core.context import add_context_item, search_context

        item_id = add_context_item(
            project_id=None,
            key="tagged_item",
            value="value",
            tags=["api", "production", "urgent"],
        )
        results = search_context(tags=["api"])
        assert any(r["key"] == "tagged_item" for r in results)

    def test_context_item_types(self, fresh_db):
        from neuralclaw.core.context import add_context_item, search_context

        add_context_item(project_id=None, key="k1", value="v1", item_type="decision")
        add_context_item(project_id=None, key="k2", value="v2", item_type="error")
        add_context_item(project_id=None, key="k3", value="v3", item_type="variable")
        add_context_item(project_id=None, key="k4", value="v4", item_type="preference")

        for item_type in ["decision", "error", "variable", "preference"]:
            results = search_context(item_type=item_type)
            assert len(results) == 1, f"Expected 1 result for type {item_type}"


class TestVault:
    """Tests for vault encryption."""

    def test_vault_init_and_set(self, fresh_db, temp_config):
        from neuralclaw.core.vault import init_vault, vault_set, vault_get

        init_vault()
        assert temp_config["vault_key_path"].exists()

        vault_set("TEST_SECRET", "my_secret_value")
        retrieved = vault_get("TEST_SECRET")
        assert retrieved == "my_secret_value"

    def test_vault_list(self, fresh_db):
        from neuralclaw.core.vault import init_vault, vault_set, vault_list

        init_vault()
        vault_set("SECRET_A", "value_a")
        vault_set("SECRET_B", "value_b")

        secrets = vault_list()
        assert "SECRET_A" in secrets
        assert "SECRET_B" in secrets

    def test_vault_delete(self, fresh_db):
        from neuralclaw.core.vault import init_vault, vault_set, vault_get, vault_delete

        init_vault()
        vault_set("TO_DELETE", "temp_value")
        assert vault_get("TO_DELETE") == "temp_value"

        vault_delete("TO_DELETE")
        assert vault_get("TO_DELETE") is None

    def test_vault_encrypted_not_plaintext(self, fresh_db, temp_config):
        from neuralclaw.core.vault import init_vault, vault_set

        init_vault()
        vault_set("MY_SECRET", "super_secret_value")

        # Read vault.db directly — should NOT contain plaintext
        vault_db = temp_config["vault_dir"] / "vault.db"
        if vault_db.exists():
            content = vault_db.read_bytes()
            assert b"super_secret_value" not in content


class TestContextBridge:
    """Tests for context export."""

    def test_export_context_basic(self, fresh_db):
        from neuralclaw.core.context import add_context_item
        from neuralclaw.core.bridge import export_context_json

        add_context_item(project_id=None, key="test_key", value="test_value", item_type="note")

        json_str = export_context_json(task="Test task", adapter_name="openclaw")
        data = json.loads(json_str)

        assert data["task"] == "Test task"
        assert data["metadata"]["adapter"] == "openclaw"
        assert data["metadata"]["total_items"] == 1
        assert len(data["context"]) == 1
        assert data["context"][0]["key"] == "test_key"

    def test_export_context_constraints(self, fresh_db):
        from neuralclaw.core.bridge import export_context_json

        json_str = export_context_json(task="Test task", adapter_name="openclaw")
        data = json.loads(json_str)

        assert "constraints" in data
        assert len(data["constraints"]) > 0

    def test_export_context_wrong_adapter(self, fresh_db):
        from neuralclaw.core.bridge import export_context_json

        with pytest.raises(ValueError, match="not found"):
            export_context_json(task="Test", adapter_name="nonexistent_adapter")
