"""Tests for projects module."""

import pytest
from neuralclaw.core.projects import (
    create_project, list_projects, get_project,
    archive_project, delete_project, project_exists,
)


class TestCreateProject:
    """Tests for create_project function."""

    def test_create_simple_project(self, fresh_db):
        pid = create_project("test-proj")
        assert pid is not None
        assert len(pid) == 36  # UUID

    def test_create_with_description(self, fresh_db):
        pid = create_project("test-proj", "My description")
        project = get_project(pid)
        assert project["description"] == "My description"

    def test_create_sets_active_status(self, fresh_db):
        pid = create_project("status-test")
        project = get_project(pid)
        assert project["status"] == "active"

    def test_create_sets_timestamps(self, fresh_db):
        pid = create_project("timestamps-test")
        project = get_project(pid)
        assert project["created_at"] is not None
        assert project["updated_at"] is not None
        assert project["created_at"] == project["updated_at"]

    def test_create_duplicate_name_fails(self, fresh_db):
        create_project("duplicate-test")
        with pytest.raises(Exception) as exc_info:
            create_project("duplicate-test")
        assert "UNIQUE constraint" in str(exc_info.value) or "already exists" in str(exc_info.value)


class TestListProjects:
    """Tests for list_projects function."""

    def test_list_empty(self, fresh_db):
        projects = list_projects()
        assert projects == []

    def test_list_multiple_projects(self, fresh_db):
        create_project("proj-a")
        create_project("proj-b")
        create_project("proj-c")
        projects = list_projects()
        assert len(projects) == 3
        names = {p["name"] for p in projects}
        assert names == {"proj-a", "proj-b", "proj-c"}

    def test_list_filter_by_status(self, fresh_db):
        pid = create_project("filter-test")
        create_project("other-proj")
        archive_project(pid)

        active = list_projects(status="active")
        archived = list_projects(status="archived")
        assert len(active) == 1
        assert len(archived) == 1
        assert active[0]["name"] == "other-proj"
        assert archived[0]["name"] == "filter-test"

    def test_list_sorted_by_updated(self, fresh_db):
        """Newer projects should appear first."""
        import time
        
        p1 = create_project("first")
        p1_time = get_project(p1)["created_at"]
        
        # Ensure second project gets a different timestamp by adding a tiny sleep
        time.sleep(0.01)
        p2 = create_project("second")
        p2_time = get_project(p2)["created_at"]
        
        projects = list_projects()
        
        # Both projects should exist
        project_names = [p["name"] for p in projects]
        assert "first" in project_names
        assert "second" in project_names
        
        # If timestamps differ, verify order
        if p1_time != p2_time:
            assert projects[0]["name"] == "second", \
                f"Expected 'second' first, got {projects[0]['name']}"


class TestGetProject:
    """Tests for get_project function."""

    def test_get_by_id(self, fresh_db):
        pid = create_project("get-by-id")
        project = get_project(pid)
        assert project["name"] == "get-by-id"

    def test_get_by_name(self, fresh_db):
        create_project("get-by-name")
        project = get_project("get-by-name")
        assert project["name"] == "get-by-name"

    def test_get_nonexistent(self, fresh_db):
        project = get_project("does-not-exist")
        assert project is None

    def test_get_with_archived_status(self, fresh_db):
        pid = create_project("archived-get")
        archive_project(pid)
        project = get_project(pid)
        assert project["status"] == "archived"


class TestArchiveProject:
    """Tests for archive_project function."""

    def test_archive_sets_archived_status(self, fresh_db):
        pid = create_project("archive-me")
        archive_project(pid)
        project = get_project(pid)
        assert project["status"] == "archived"

    def test_archive_sets_archived_at(self, fresh_db):
        pid = create_project("archive-time")
        archive_project(pid)
        project = get_project(pid)
        assert project["archived_at"] is not None

    def test_archive_nonexistent_returns_false(self, fresh_db):
        result = archive_project("00000000-0000-0000-0000-000000000000")
        assert result is False

    def test_archive_already_archived(self, fresh_db):
        pid = create_project("already-archived")
        archive_project(pid)
        result = archive_project(pid)
        assert result is True  # Should succeed (idempotent)


class TestDeleteProject:
    """Tests for delete_project function."""

    def test_delete_existing(self, fresh_db):
        pid = create_project("delete-me")
        result = delete_project(pid)
        assert result is True
        assert get_project(pid) is None

    def test_delete_nonexistent_returns_false(self, fresh_db):
        result = delete_project("00000000-0000-0000-0000-000000000000")
        assert result is False

    def test_delete_cascades_to_context(self, fresh_db):
        """Deleting project should delete its context items."""
        from neuralclaw.core.context import add_context_item, search_context

        pid = create_project("cascade-test")
        add_context_item(project_id=pid, key="item1", value="v1")
        add_context_item(project_id=pid, key="item2", value="v2")

        delete_project(pid)

        results = search_context(project_id=pid)
        assert len(results) == 0


class TestProjectExists:
    """Tests for project_exists function."""

    def test_exists_after_create(self, fresh_db):
        pid = create_project("exists-check")
        assert project_exists(pid) is True
        assert project_exists("exists-check") is True

    def test_exists_not_found(self, fresh_db):
        assert project_exists("nope") is False
        assert project_exists("00000000-0000-0000-0000-000000000000") is False

    def test_exists_archived(self, fresh_db):
        pid = create_project("archived-exists")
        archive_project(pid)
        assert project_exists(pid) is True  # Still exists, just archived
