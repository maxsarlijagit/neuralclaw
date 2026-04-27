"""Project management."""

import uuid
import time
from typing import Any

from neuralclaw.db.connection import get_connection


def create_project(name: str, description: str = "") -> str:
    """Create a new project."""
    project_id = str(uuid.uuid4())
    now = int(time.time())

    with get_connection() as conn:
        conn.execute("""
            INSERT INTO projects (id, name, description, status, created_at, updated_at)
            VALUES (?, ?, ?, 'active', ?, ?)
        """, (project_id, name, description, now, now))

    return project_id


def list_projects(status: str | None = None) -> list[dict[str, Any]]:
    """List all projects, optionally filtered by status."""
    sql = "SELECT * FROM projects"
    params = []
    if status is not None:
        sql += " WHERE status = ?"
        params.append(status)
    sql += " ORDER BY updated_at DESC"

    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()

    return [dict(row) for row in rows]


def get_project(project_id: str) -> dict[str, Any] | None:
    """Get a project by ID or name."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM projects WHERE id = ? OR name = ?",
            (project_id, project_id)
        ).fetchone()

    return dict(row) if row else None


def archive_project(project_id: str) -> bool:
    """Archive a project."""
    now = int(time.time())
    with get_connection() as conn:
        cur = conn.execute(
            "UPDATE projects SET status = 'archived', archived_at = ?, updated_at = ? WHERE id = ?",
            (now, now, project_id)
        )
    return cur.rowcount > 0


def delete_project(project_id: str) -> bool:
    """Delete a project and all its context items."""
    with get_connection() as conn:
        cur = conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    return cur.rowcount > 0


def project_exists(project_id: str) -> bool:
    """Check if a project exists by ID or name."""
    return get_project(project_id) is not None
