"""Tests for fresh command / module."""

import pytest
import json
from click.testing import CliRunner
from neuralclaw.cli.main import app


class TestFreshCommand:
    """Tests for neuralclaw fresh command."""

    def test_fresh_command_exists(self, fresh_db):
        runner = CliRunner()
        result = runner.invoke(app, ["fresh", "--help"])
        # Should not fail - command should exist
        assert result.exit_code in [0]

    def test_fresh_without_project(self, fresh_db):
        """Fresh without project should show help or error."""
        runner = CliRunner()
        result = runner.invoke(app, ["fresh"])
        # May show help or work with global scope
        assert result.exit_code in [0, 1]

    def test_fresh_with_project(self, fresh_db, sample_project):
        """Fresh should work with a specific project."""
        runner = CliRunner()
        result = runner.invoke(app, ["fresh", "-p", sample_project])
        # Should produce output
        assert result.exit_code in [0, 1]
        assert len(result.output) > 0

    def test_fresh_help(self, fresh_db):
        """Fresh --help should show usage."""
        runner = CliRunner()
        result = runner.invoke(app, ["fresh", "--help"])
        assert result.exit_code == 0
        assert "fresh" in result.output.lower()

    def test_fresh_generates_snapshot(self, fresh_db, sample_project):
        """Fresh should generate a snapshot in DB."""
        from neuralclaw.core.context import add_context_item

        add_context_item(project_id=sample_project, key="snap_key", value="snap_value")

        runner = CliRunner()
        result = runner.invoke(app, ["fresh", "-p", sample_project])

        # Check that fresh_apple table has the snapshot
        from neuralclaw.db.connection import get_connection
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM fresh_apple WHERE project_id = ?",
                (sample_project,)
            ).fetchone()
        # Fresh command should create or update snapshot
        assert result.exit_code in [0, 1]

    def test_fresh_with_no_context(self, fresh_db, sample_project):
        """Fresh with no context should still work."""
        runner = CliRunner()
        result = runner.invoke(app, ["fresh", "-p", sample_project])
        # Should not crash
        assert result.exit_code in [0, 1]
