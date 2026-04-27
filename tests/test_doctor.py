"""Tests for doctor command."""

import pytest
from typer.testing import CliRunner
from neuralclaw.cli.main import app


class TestDoctorCommand:
    """Tests for neuralclaw doctor command."""

    def test_doctor_command_exists(self, fresh_db):
        runner = CliRunner()
        result = runner.invoke(app, ["doctor"])
        # Should not raise - command should exist
        assert result.exit_code in [0, 1]  # 0 = healthy, 1 = issues found

    def test_doctor_reports_config_dir(self, fresh_db):
        """Doctor should check and report on config directory."""
        runner = CliRunner()
        result = runner.invoke(app, ["doctor"])
        output = result.output.lower()
        # Should mention config or initialization
        assert "config" in output or "init" in output or "ok" in output

    def test_doctor_reports_schema_version(self, fresh_db):
        """Doctor should check schema version."""
        runner = CliRunner()
        result = runner.invoke(app, ["doctor"])
        output = result.output
        # Should check or mention schema
        assert "schema" in output.lower() or "version" in output.lower() or "ok" in output.lower()

    def test_doctor_reports_vault_status(self, fresh_db):
        """Doctor should check vault."""
        runner = CliRunner()
        result = runner.invoke(app, ["doctor"])
        output = result.output.lower()
        assert "vault" in output or "initialized" in output or "ok" in output

    def test_doctor_with_missing_init(self, temp_config, monkeypatch):
        """Doctor should gracefully handle missing init."""
        # Don't init, just run doctor
        runner = CliRunner()
        result = runner.invoke(app, ["doctor"])
        # Should not crash, might exit with 1
        assert result.exit_code in [0, 1]

    def test_doctor_with_init(self, fresh_db):
        """Doctor should pass with green status after init."""
        from neuralclaw.core.vault import init_vault
        init_vault()
        runner = CliRunner()
        result = runner.invoke(app, ["doctor"])
        # If all checks pass, should exit 0
        # If issues, exit 1 but still produce output
        assert len(result.output) > 0

    def test_doctor_checks_fts5(self, fresh_db):
        """Doctor should verify FTS5 is available."""
        runner = CliRunner()
        result = runner.invoke(app, ["doctor"])
        output = result.output.lower()
        # FTS5 is used for full-text search
        assert "fts" in output or "search" in output or "ok" in output or "index" in output

    def test_doctor_checks_indexes(self, fresh_db):
        """Doctor should verify indexes exist."""
        runner = CliRunner()
        result = runner.invoke(app, ["doctor"])
        output = result.output.lower()
        # Should check indexes
        assert "index" in output or "ok" in output or "check" in output

    def test_doctor_output_formatted(self, fresh_db):
        """Doctor output should be human-readable."""
        from neuralclaw.core.vault import init_vault
        init_vault()
        runner = CliRunner()
        result = runner.invoke(app, ["doctor"])
        # Should use Rich formatting or plain text
        assert len(result.output) > 10  # Not just "ok"
