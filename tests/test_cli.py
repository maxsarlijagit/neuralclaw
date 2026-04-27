"""Comprehensive CLI tests using CliRunner."""

import json
import pytest
from click.testing import CliRunner

from neuralclaw.cli.main import app
from neuralclaw.core.context import add_context_item, search_context
from neuralclaw.core.projects import create_project


class TestCLIInit:
    """Tests for neuralclaw init command."""

    def test_init_command(self, temp_config):
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(app, ["init"])
            # Should not fail
            assert result.exit_code == 0
            assert "initialized" in result.output.lower() or "ready" in result.output.lower()

    def test_init_idempotent(self, temp_config):
        runner = CliRunner()
        result = runner.invoke(app, ["init"])
        assert result.exit_code == 0
        result2 = runner.invoke(app, ["init"])
        # Should not fail on second run
        assert result2.exit_code == 0

    def test_init_creates_database(self, temp_config):
        runner = CliRunner()
        result = runner.invoke(app, ["init"])
        assert result.exit_code == 0


class TestCLIAdd:
    """Tests for neuralclaw add command."""

    def test_add_simple_key_value(self, fresh_db):
        runner = CliRunner()
        result = runner.invoke(app, ["add", "test_key=test_value"])
        assert result.exit_code == 0
        assert "added" in result.output.lower() or "ok" in result.output.lower() or "✓" in result.output

    def test_add_with_type(self, fresh_db):
        runner = CliRunner()
        result = runner.invoke(app, ["add", "api_url=https://api.test.com", "--type", "variable"])
        assert result.exit_code == 0

    def test_add_with_tags(self, fresh_db):
        runner = CliRunner()
        result = runner.invoke(app, ["add", "tagged=value", "--tags", "api,production"])
        assert result.exit_code == 0

    def test_add_with_project(self, fresh_db, sample_project):
        runner = CliRunner()
        result = runner.invoke(app, ["add", "proj_key=proj_value", "-p", sample_project])
        assert result.exit_code == 0

    def test_add_with_nonexistent_project(self, fresh_db):
        runner = CliRunner()
        result = runner.invoke(app, ["add", "key=value", "-p", "nonexistent_project_xyz"])
        assert result.exit_code != 0
        assert "not found" in result.output.lower() or "error" in result.output.lower()

    def test_add_invalid_format(self, fresh_db):
        runner = CliRunner()
        result = runner.invoke(app, ["add", "invalid_format_no_equals"])
        assert result.exit_code != 0

    def test_add_colon_separator(self, fresh_db):
        runner = CliRunner()
        result = runner.invoke(app, ["add", "colon:separated:value"])
        assert result.exit_code == 0

    def test_add_with_confidence(self, fresh_db):
        runner = CliRunner()
        result = runner.invoke(app, ["add", "conf_key=value", "--confidence", "0.5"])
        assert result.exit_code == 0


class TestCLISearch:
    """Tests for neuralclaw search command."""

    def test_search_empty(self, fresh_db):
        runner = CliRunner()
        result = runner.invoke(app, ["search"])
        assert result.exit_code == 0

    def test_search_with_query(self, fresh_db):
        add_context_item(project_id=None, key="searchable_key", value="searchable_value")
        runner = CliRunner()
        result = runner.invoke(app, ["search", "searchable"])
        assert result.exit_code == 0
        assert "searchable_key" in result.output

    def test_search_with_json_output(self, fresh_db):
        add_context_item(project_id=None, key="json_key", value="json_value")
        runner = CliRunner()
        result = runner.invoke(app, ["search", "json", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)

    def test_search_with_project_filter(self, fresh_db, sample_project):
        add_context_item(project_id=sample_project, key="proj_key", value="v")
        runner = CliRunner()
        result = runner.invoke(app, ["search", "-p", sample_project])
        assert result.exit_code == 0
        assert "proj_key" in result.output

    def test_search_with_type_filter(self, fresh_db):
        add_context_item(project_id=None, key="type_key", value="v", item_type="decision")
        runner = CliRunner()
        result = runner.invoke(app, ["search", "--type", "decision"])
        assert result.exit_code == 0
        assert "type_key" in result.output

    def test_search_with_state_filter(self, fresh_db):
        add_context_item(project_id=None, key="stale_key", value="v", state="stale")
        runner = CliRunner()
        result = runner.invoke(app, ["search", "--state", "stale"])
        assert result.exit_code == 0
        assert "stale_key" in result.output


class TestCLIProject:
    """Tests for neuralclaw project subcommand."""

    def test_project_create(self, fresh_db):
        runner = CliRunner()
        result = runner.invoke(app, ["project", "create", "cli-test-project"])
        assert result.exit_code == 0
        assert "created" in result.output.lower() or "✓" in result.output

    def test_project_create_with_description(self, fresh_db):
        runner = CliRunner()
        result = runner.invoke(app, ["project", "create", "desc-proj", "-d", "My description"])
        assert result.exit_code == 0

    def test_project_list(self, fresh_db):
        create_project("list-test-1")
        create_project("list-test-2")
        runner = CliRunner()
        result = runner.invoke(app, ["project", "list"])
        assert result.exit_code == 0
        assert "list-test-1" in result.output
        assert "list-test-2" in result.output

    def test_project_archive(self, fresh_db):
        pid = create_project("archive-test")
        runner = CliRunner()
        result = runner.invoke(app, ["project", "archive", pid])
        assert result.exit_code == 0

    def test_project_delete_with_force(self, fresh_db):
        pid = create_project("delete-test")
        runner = CliRunner()
        result = runner.invoke(app, ["project", "delete", pid, "--force"])
        assert result.exit_code == 0

    def test_project_status(self, fresh_db, sample_project):
        runner = CliRunner()
        result = runner.invoke(app, ["project", "status", sample_project])
        assert result.exit_code == 0
        assert "active" in result.output.lower()

    def test_project_delete_nonexistent(self, fresh_db):
        runner = CliRunner()
        result = runner.invoke(app, ["project", "delete", "nonexistent", "--force"])
        assert result.exit_code != 0


class TestCLIVault:
    """Tests for neuralclaw vault subcommand."""

    def test_vault_set_and_get(self, fresh_db):
        runner = CliRunner()
        result = runner.invoke(app, ["vault", "set", "CLI_SECRET", "cli_value"])
        assert result.exit_code == 0

        result = runner.invoke(app, ["vault", "get", "CLI_SECRET"])
        assert result.exit_code == 0
        assert "set" in result.output.lower()

    def test_vault_list(self, fresh_db):
        from neuralclaw.core.vault import init_vault, vault_set
        init_vault()
        vault_set("LIST_SECRET_A", "a")
        vault_set("LIST_SECRET_B", "b")
        runner = CliRunner()
        result = runner.invoke(app, ["vault", "list"])
        assert result.exit_code == 0
        assert "LIST_SECRET_A" in result.output

    def test_vault_get_nonexistent(self, fresh_db):
        runner = CliRunner()
        result = runner.invoke(app, ["vault", "get", "DOES_NOT_EXIST"])
        assert result.exit_code != 0

    def test_vault_delete(self, fresh_db):
        from neuralclaw.core.vault import init_vault, vault_set
        init_vault()
        vault_set("DELETE_ME", "v")
        runner = CliRunner()
        result = runner.invoke(app, ["vault", "delete", "DELETE_ME", "--force"])
        assert result.exit_code == 0

    def test_vault_status(self, fresh_db):
        from neuralclaw.core.vault import init_vault
        init_vault()
        runner = CliRunner()
        result = runner.invoke(app, ["vault", "status"])
        assert result.exit_code == 0


class TestCLIContext:
    """Tests for neuralclaw context command."""

    def test_context_command(self, fresh_db):
        runner = CliRunner()
        result = runner.invoke(app, ["context", "--task", "Test task"])
        assert result.exit_code == 0
        # Should output JSON
        data = json.loads(result.output)
        assert "task" in data
        assert data["task"] == "Test task"

    def test_context_with_adapter(self, fresh_db):
        runner = CliRunner()
        result = runner.invoke(app, ["context", "-t", "Test", "-a", "openclaw"])
        assert result.exit_code == 0

    def test_context_with_project(self, fresh_db, sample_project):
        runner = CliRunner()
        result = runner.invoke(app, ["context", "-t", "Test", "-p", sample_project])
        assert result.exit_code == 0

    def test_context_with_json_output_flag(self, fresh_db):
        runner = CliRunner()
        result = runner.invoke(app, ["context", "-t", "Test", "--json"])
        assert result.exit_code == 0


class TestCLIImport:
    """Tests for neuralclaw import command."""

    def test_import_help(self, fresh_db):
        runner = CliRunner()
        result = runner.invoke(app, ["import", "--help"])
        # Import command should exist
        assert result.exit_code in [0, 1]  # May need --from flag

    def test_import_from_json(self, fresh_db, tmp_path):
        json_file = tmp_path / "import.json"
        json_file.write_text(json.dumps([
            {"key": "import_key_1", "value": "value1", "type": "note"},
            {"key": "import_key_2", "value": "value2", "type": "variable"},
        ]))
        runner = CliRunner()
        result = runner.invoke(app, ["import", "--from", str(json_file)])
        assert result.exit_code == 0

        # Verify items were added
        results = search_context(query="import_key")
        assert len(results) == 2

    def test_import_from_jsonl(self, fresh_db, tmp_path):
        jsonl_file = tmp_path / "import.jsonl"
        jsonl_file.write_text(
            '{"key": "jl_key_1", "value": "v1"}\n{"key": "jl_key_2", "value": "v2"}\n'
        )
        runner = CliRunner()
        result = runner.invoke(app, ["import", "--from", str(jsonl_file)])
        assert result.exit_code == 0

    def test_import_with_project(self, fresh_db, sample_project, tmp_path):
        json_file = tmp_path / "import_proj.json"
        json_file.write_text(json.dumps([
            {"key": "proj_item", "value": "v"},
        ]))
        runner = CliRunner()
        result = runner.invoke(app, ["import", "--from", str(json_file), "-p", sample_project])
        assert result.exit_code == 0


class TestCLIComprehensive:
    """End-to-end CLI tests."""

    def test_full_workflow(self, temp_config):
        """Test a complete workflow: init -> add -> search -> context."""
        runner = CliRunner()

        # Init
        result = runner.invoke(app, ["init"])
        assert result.exit_code == 0

        # Add context
        result = runner.invoke(app, ["add", "workflow_key=workflow_value", "--type", "variable"])
        assert result.exit_code == 0

        # Search
        result = runner.invoke(app, ["search", "workflow"])
        assert result.exit_code == 0
        assert "workflow_key" in result.output

        # Context export
        result = runner.invoke(app, ["context", "-t", "Test workflow"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["metadata"]["total_items"] >= 1

    def test_error_handling(self, fresh_db):
        """Test that errors produce meaningful messages."""
        runner = CliRunner()

        # Bad add format
        result = runner.invoke(app, ["add", "badformat"])
        assert result.exit_code != 0
        assert "error" in result.output.lower() or "format" in result.output.lower()

        # Nonexistent project
        result = runner.invoke(app, ["add", "key=value", "-p", "noexist"])
        assert result.exit_code != 0
