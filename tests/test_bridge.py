"""Tests for context bridge module."""

import json
import pytest

from neuralclaw.core.bridge import (
    load_adapter, build_context_export, export_context_json,
)
from neuralclaw.core.context import add_context_item


class TestLoadAdapter:
    """Tests for load_adapter function."""

    def test_load_openclaw_adapter(self, fresh_db):
        adapter = load_adapter("openclaw")
        assert adapter is not None
        assert "constraints" in adapter

    def test_load_chatgpt_adapter(self, fresh_db):
        adapter = load_adapter("chatgpt")
        assert adapter is not None

    def test_load_claude_adapter(self, fresh_db):
        adapter = load_adapter("claude")
        assert adapter is not None

    def test_load_nonexistent_adapter_raises(self, fresh_db):
        with pytest.raises(ValueError, match="not found"):
            load_adapter("nonexistent")


class TestBuildContextExport:
    """Tests for build_context_export function."""

    def test_export_includes_task(self, fresh_db):
        export = build_context_export(
            task="Test task",
            adapter_name="openclaw",
        )
        assert export["task"] == "Test task"

    def test_export_includes_metadata(self, fresh_db):
        export = build_context_export(
            task="Test",
            adapter_name="openclaw",
        )
        assert "metadata" in export
        assert export["metadata"]["adapter"] == "openclaw"
        assert "total_items" in export["metadata"]
        assert "tokens_estimate" in export["metadata"]

    def test_export_includes_context_items(self, fresh_db):
        add_context_item(project_id=None, key="test_key", value="test_value")
        export = build_context_export(
            task="Test",
            adapter_name="openclaw",
        )
        assert len(export["context"]) == 1
        assert export["context"][0]["key"] == "test_key"

    def test_export_includes_constraints(self, fresh_db):
        export = build_context_export(
            task="Test",
            adapter_name="openclaw",
        )
        assert "constraints" in export
        assert isinstance(export["constraints"], list)

    def test_export_filters_to_active_by_default(self, fresh_db):
        add_context_item(project_id=None, key="active_key", value="v", state="active")
        add_context_item(project_id=None, key="stale_key", value="v", state="stale")
        export = build_context_export(
            task="Test",
            adapter_name="openclaw",
        )
        keys = {c["key"] for c in export["context"]}
        assert "active_key" in keys
        assert "stale_key" not in keys

    def test_export_with_query_filter(self, fresh_db):
        add_context_item(project_id=None, key="api_key", value="v")
        add_context_item(project_id=None, key="db_key", value="v")
        export = build_context_export(
            task="Test",
            adapter_name="openclaw",
            query="api",
        )
        assert len(export["context"]) == 1
        assert export["context"][0]["key"] == "api_key"

    def test_export_warnings_for_stale_items(self, fresh_db):
        import time
        past = int(time.time()) - 1000
        add_context_item(
            project_id=None,
            key="stale_item",
            value="old",
            stale_after=past,
        )
        export = build_context_export(
            task="Test",
            adapter_name="openclaw",
        )
        assert len(export["warnings"]) > 0
        assert any("stale" in w.lower() for w in export["warnings"])

    def test_export_sources_contains_project_info(self, fresh_db):
        export = build_context_export(
            task="Test",
            project_id=None,
            adapter_name="openclaw",
        )
        assert "sources" in export
        assert any("context_items" in s for s in export["sources"])


class TestExportContextJson:
    """Tests for export_context_json function."""

    def test_json_output_valid_json(self, fresh_db):
        add_context_item(project_id=None, key="json_key", value="json_value")
        json_str = export_context_json(task="Test", adapter_name="openclaw")
        data = json.loads(json_str)
        assert data["task"] == "Test"

    def test_json_output_pretty_formatted(self, fresh_db):
        json_str = export_context_json(task="Test", adapter_name="openclaw")
        # Check that it's pretty-printed (has indentation)
        assert "\n" in json_str

    def test_json_output_with_project(self, fresh_db, sample_project):
        add_context_item(project_id=sample_project, key="proj_key", value="v")
        json_str = export_context_json(
            task="Test",
            project_id=sample_project,
            adapter_name="openclaw",
        )
        data = json.loads(json_str)
        assert data["metadata"]["project"] == sample_project

    def test_json_output_unknown_adapter_raises(self, fresh_db):
        with pytest.raises(ValueError):
            export_context_json(task="Test", adapter_name="unknown_adapter")
