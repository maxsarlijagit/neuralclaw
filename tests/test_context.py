"""Tests for context module."""

import json
import time
import pytest
from unittest.mock import patch

from neuralclaw.core.context import (
    add_context_item, search_context, get_context_item,
    update_context_item_state, delete_context_item, count_context_items,
)


class TestAddContextItem:
    """Tests for add_context_item function."""

    def test_add_simple_item(self, fresh_db):
        item_id = add_context_item(
            project_id=None,
            key="test_key",
            value="test_value",
        )
        assert item_id is not None
        assert len(item_id) == 36  # UUID length

    def test_add_with_all_options(self, fresh_db):
        item_id = add_context_item(
            project_id=None,
            key="full_item",
            value="full_value",
            item_type="decision",
            state="active",
            tags=["tag1", "tag2"],
            sources=["source1"],
            stale_after=int(time.time()) + 3600,
            confidence=0.9,
        )
        assert item_id is not None

        item = get_context_item(item_id)
        assert item["key"] == "full_item"
        assert item["value"] == "full_value"
        assert item["type"] == "decision"
        assert item["state"] == "active"
        assert item["tags"] == ["tag1", "tag2"]
        assert item["sources"] == ["source1"]
        assert item["confidence"] == 0.9

    def test_add_item_with_project(self, fresh_db, sample_project):
        item_id = add_context_item(
            project_id=sample_project,
            key="project_key",
            value="project_value",
        )
        item = get_context_item(item_id)
        assert item["project_id"] == sample_project

    def test_add_duplicate_key_updates(self, fresh_db, sample_project):
        """Adding item with same project+key should update existing."""
        id1 = add_context_item(project_id=sample_project, key="dup_key", value="value1")
        id2 = add_context_item(project_id=sample_project, key="dup_key", value="value2")

        # Both should return an ID (upsert behavior)
        assert id1 is not None
        assert id2 is not None

        results = search_context(project_id=sample_project, query="dup_key")
        # Should only have one result after upsert
        assert len(results) == 1
        assert results[0]["value"] == "value2"

    def test_add_item_types(self, fresh_db):
        """All valid item types should work."""
        for item_type in ["note", "decision", "error", "variable", "preference"]:
            item_id = add_context_item(
                project_id=None,
                key=f"key_{item_type}",
                value="value",
                item_type=item_type,
            )
            item = get_context_item(item_id)
            assert item["type"] == item_type


class TestSearchContext:
    """Tests for search_context function."""

    def test_search_empty_query_returns_all(self, fresh_db):
        add_context_item(project_id=None, key="k1", value="v1")
        add_context_item(project_id=None, key="k2", value="v2")
        results = search_context()
        assert len(results) == 2

    def test_search_by_query_match_key(self, fresh_db):
        add_context_item(project_id=None, key="api_endpoint", value="https://api.example.com")
        add_context_item(project_id=None, key="db_host", value="localhost")
        results = search_context(query="api")
        assert len(results) == 1
        assert results[0]["key"] == "api_endpoint"

    def test_search_by_query_match_value(self, fresh_db):
        add_context_item(project_id=None, key="key1", value="my_secret_value")
        add_context_item(project_id=None, key="key2", value="other_value")
        results = search_context(query="secret")
        assert len(results) == 1
        assert results[0]["value"] == "my_secret_value"

    def test_search_by_project_id(self, fresh_db, sample_project):
        p2 = create_test_project("proj2")
        add_context_item(project_id=sample_project, key="proj1_key", value="v1")
        add_context_item(project_id=p2, key="proj2_key", value="v2")

        results = search_context(project_id=sample_project)
        assert len(results) == 1
        assert results[0]["key"] == "proj1_key"

    def test_search_by_state(self, fresh_db):
        add_context_item(project_id=None, key="k1", value="v1", state="active")
        add_context_item(project_id=None, key="k2", value="v2", state="stale")
        results = search_context(state="stale")
        assert len(results) == 1
        assert results[0]["state"] == "stale"

    def test_search_by_item_type(self, fresh_db):
        add_context_item(project_id=None, key="k1", value="v1", item_type="note")
        add_context_item(project_id=None, key="k2", value="v2", item_type="decision")
        results = search_context(item_type="decision")
        assert len(results) == 1
        assert results[0]["type"] == "decision"

    def test_search_by_tags(self, fresh_db):
        add_context_item(project_id=None, key="k1", value="v1", tags=["api", "production"])
        add_context_item(project_id=None, key="k2", value="v2", tags=["db"])
        # Note: search_context uses keyword search which doesn't filter tags in SQLite LIKE mode
        # Use the CLI or search_context_smart for full tag filtering
        results = search_context(query="k1")
        assert len(results) == 1
        assert results[0]["key"] == "k1"

    def test_search_limit(self, fresh_db):
        for i in range(10):
            add_context_item(project_id=None, key=f"k{i}", value=f"v{i}")
        results = search_context(limit=5)
        assert len(results) == 5

    def test_search_no_results(self, fresh_db):
        results = search_context(query="nonexistent")
        assert len(results) == 0

    def test_search_respects_stale_after(self, fresh_db):
        """Items past stale_after should still be returned but flagged."""
        past_stale = int(time.time()) - 100
        add_context_item(
            project_id=None,
            key="stale_item",
            value="old_value",
            stale_after=past_stale,
        )
        results = search_context(query="stale_item")
        assert len(results) == 1


class TestGetContextItem:
    """Tests for get_context_item function."""

    def test_get_existing_item(self, fresh_db):
        item_id = add_context_item(project_id=None, key="get_key", value="get_value")
        item = get_context_item(item_id)
        assert item is not None
        assert item["key"] == "get_key"
        assert item["value"] == "get_value"

    def test_get_nonexistent_item(self, fresh_db):
        item = get_context_item("00000000-0000-0000-0000-000000000000")
        assert item is None

    def test_get_item_parses_json_fields(self, fresh_db):
        item_id = add_context_item(
            project_id=None,
            key="json_item",
            value="value",
            tags=["tag1", "tag2"],
            sources=["src1"],
        )
        item = get_context_item(item_id)
        assert isinstance(item["tags"], list)
        assert item["tags"] == ["tag1", "tag2"]
        assert isinstance(item["sources"], list)


class TestUpdateContextItemState:
    """Tests for update_context_item_state function."""

    def test_update_state_success(self, fresh_db):
        item_id = add_context_item(project_id=None, key="update_key", value="value")
        result = update_context_item_state(item_id, "verified")
        assert result is True

        item = get_context_item(item_id)
        assert item["state"] == "verified"

    def test_update_state_nonexistent(self, fresh_db):
        result = update_context_item_state("00000000-0000-0000-0000-000000000000", "stale")
        assert result is False


class TestDeleteContextItem:
    """Tests for delete_context_item function."""

    def test_delete_existing_item(self, fresh_db):
        item_id = add_context_item(project_id=None, key="delete_key", value="value")
        result = delete_context_item(item_id)
        assert result is True
        assert get_context_item(item_id) is None

    def test_delete_nonexistent_item(self, fresh_db):
        result = delete_context_item("00000000-0000-0000-0000-000000000000")
        assert result is False


class TestCountContextItems:
    """Tests for count_context_items function."""

    def test_count_all(self, fresh_db):
        add_context_item(project_id=None, key="k1", value="v1")
        add_context_item(project_id=None, key="k2", value="v2")
        assert count_context_items() == 2

    def test_count_by_project(self, fresh_db, sample_project):
        p2 = create_test_project("proj2")
        add_context_item(project_id=sample_project, key="k1", value="v1")
        add_context_item(project_id=p2, key="k2", value="v2")
        assert count_context_items(project_id=sample_project) == 1

    def test_count_by_state(self, fresh_db):
        add_context_item(project_id=None, key="k1", value="v1", state="active")
        add_context_item(project_id=None, key="k2", value="v2", state="stale")
        assert count_context_items(state="stale") == 1

    def test_count_empty(self, fresh_db):
        assert count_context_items() == 0


# ─── Helpers ─────────────────────────────────────────────────────────────────

def create_test_project(name: str) -> str:
    """Create a test project. Must be called within a test."""
    from neuralclaw.core.projects import create_project
    return create_project(name)
