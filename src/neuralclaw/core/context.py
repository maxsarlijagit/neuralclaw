"""Context engine - search, rank, and manage context items."""

import uuid
import json
import time
import sqlite3
from typing import Any

from neuralclaw.db.connection import get_connection


def add_context_item(
    project_id: str | None,
    key: str,
    value: str,
    item_type: str = "note",
    state: str = "active",
    tags: list[str] | None = None,
    sources: list[str] | None = None,
    stale_after: int | None = None,
    confidence: float = 1.0,
) -> str:
    """Add a new context item.

    On conflict (same project_id + key):
    - If value is identical: no-op (idempotent)
    - If value is different: mark BOTH old and new as 'conflicting'
    """
    item_id = str(uuid.uuid4())
    now = int(time.time())

    with get_connection() as conn:
        # Check for existing item with same key (for conflict detection)
        # Use NULL-safe comparison: (project_id = ? OR (project_id IS NULL AND ? IS NULL))
        null_safe_clause = (
            "(project_id = ? OR (project_id IS NULL AND ? IS NULL))"
            if project_id is None
            else "project_id = ?"
        )
        if project_id is None:
            existing = conn.execute(
                f"SELECT id, value, state FROM context_items WHERE {null_safe_clause} AND key = ?",
                (project_id, project_id, key)
            ).fetchone()
        else:
            existing = conn.execute(
                f"SELECT id, value, state FROM context_items WHERE {null_safe_clause} AND key = ?",
                (project_id, key)
            ).fetchone()

        if existing:
            existing_value = existing["value"]
            existing_id = existing["id"]
            if existing_value != value:
                # Different value for same key → CONFLICT
                # Mark existing as conflicting
                conn.execute(
                    "UPDATE context_items SET state = 'conflicting', updated_at = ? WHERE id = ?",
                    (now, existing_id)
                )
                # Insert new one as conflicting too (separate transaction to avoid UNIQUE conflict)
                # Use INSERT OR IGNORE then UPDATE, or just do a raw insert
                try:
                    conn.execute("""
                        INSERT INTO context_items
                        (id, project_id, key, value, type, state, tags, sources, created_at, updated_at, stale_after, confidence)
                        VALUES (?, ?, ?, ?, ?, 'conflicting', ?, ?, ?, ?, ?, ?)
                    """, (
                        item_id,
                        project_id,
                        key,
                        value,
                        item_type,
                        json.dumps(tags or []),
                        json.dumps(sources or []),
                        now,
                        now,
                        stale_after,
                        confidence,
                    ))
                except sqlite3.IntegrityError:
                    # Item already exists and was marked conflicting by another call — update it
                    conn.execute("""
                        UPDATE context_items SET value = ?, type = ?, state = 'conflicting',
                        tags = ?, sources = ?, updated_at = ?, stale_after = ?, confidence = ?
                        WHERE project_id IS ? AND key = ?
                    """, (
                        value, item_type,
                        json.dumps(tags or []), json.dumps(sources or []),
                        now, stale_after, confidence,
                        project_id, key,
                    ))
                    item_id = existing_id  # already exists as conflicting
                return item_id
            else:
                # Same value — idempotent update, preserve existing state (don't un-conflict)
                existing_state = existing["state"]
                conn.execute("""
                    INSERT INTO context_items
                    (id, project_id, key, value, type, state, tags, sources, created_at, updated_at, stale_after, confidence)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(project_id, key) DO UPDATE SET
                        value = excluded.value,
                        type = excluded.type,
                        tags = excluded.tags,
                        sources = excluded.sources,
                        updated_at = excluded.updated_at,
                        stale_after = excluded.stale_after,
                        confidence = excluded.confidence
                """, (
                    item_id,
                    project_id,
                    key,
                    value,
                    item_type,
                    existing_state,  # preserve existing state (e.g. don't un-conflict)
                    json.dumps(tags or []),
                    json.dumps(sources or []),
                    now,
                    now,
                    stale_after,
                    confidence,
                ))
                return existing_id

        # No conflict — regular insert
        conn.execute("""
            INSERT INTO context_items
            (id, project_id, key, value, type, state, tags, sources, created_at, updated_at, stale_after, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            item_id,
            project_id,
            key,
            value,
            item_type,
            state,
            json.dumps(tags or []),
            json.dumps(sources or []),
            now,
            now,
            stale_after,
            confidence,
        ))

    return item_id


def search_context(
    query: str | None = None,
    project_id: str | None = None,
    state: str | None = None,
    item_type: str | None = None,
    tags: list[str] | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Search context items with filters."""
    sql_parts = ["SELECT * FROM context_items WHERE 1=1"]
    params = []

    if project_id is not None:
        sql_parts.append("AND project_id = ?")
        params.append(project_id)

    if state is not None:
        sql_parts.append("AND state = ?")
        params.append(state)

    if item_type is not None:
        sql_parts.append("AND type = ?")
        params.append(item_type)

    if query:
        sql_parts.append("AND (key LIKE ? OR value LIKE ?)")
        params.extend([f"%{query}%", f"%{query}%"])

    sql_parts.append("ORDER BY updated_at DESC LIMIT ?")
    params.append(limit)

    with get_connection() as conn:
        rows = conn.execute(" ".join(sql_parts), params).fetchall()

    results = []
    now = int(time.time())
    for row in rows:
        r = dict(row)
        # Parse JSON fields
        r["tags"] = json.loads(r["tags"]) if r["tags"] else []
        r["sources"] = json.loads(r["sources"]) if r["sources"] else []
        # Stale detection: flag items past their TTL
        if r.get("stale_after") and r["stale_after"] < now:
            r["stale_warning"] = True
        else:
            r["stale_warning"] = False
        results.append(r)

    return results


def get_context_item(item_id: str) -> dict[str, Any] | None:
    """Get a single context item by ID."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM context_items WHERE id = ?", (item_id,)
        ).fetchone()

    if not row:
        return None

    r = dict(row)
    r["tags"] = json.loads(r["tags"]) if r["tags"] else []
    r["sources"] = json.loads(r["sources"]) if r["sources"] else []
    return r


def update_context_item_state(item_id: str, state: str) -> bool:
    """Update the state of a context item."""
    with get_connection() as conn:
        cur = conn.execute(
            "UPDATE context_items SET state = ?, updated_at = ? WHERE id = ?",
            (state, int(time.time()), item_id)
        )
    return cur.rowcount > 0


def delete_context_item(item_id: str) -> bool:
    """Delete a context item."""
    with get_connection() as conn:
        cur = conn.execute(
            "DELETE FROM context_items WHERE id = ?", (item_id,)
        )
    return cur.rowcount > 0


def count_context_items(project_id: str | None = None, state: str | None = None) -> int:
    """Count context items matching filters."""
    sql = "SELECT COUNT(*) FROM context_items WHERE 1=1"
    params = []
    if project_id is not None:
        sql += " AND project_id = ?"
        params.append(project_id)
    if state is not None:
        sql += " AND state = ?"
        params.append(state)

    with get_connection() as conn:
        row = conn.execute(sql, params).fetchone()
    return row[0] if row else 0


def bulk_import_context(
    items: list[dict[str, Any]],
    project_id: str | None = None,
    batch_size: int = 50,
) -> dict[str, int]:
    """Import multiple context items in batches.
    
    Returns dict with 'added' and 'errors' counts.
    """
    added = 0
    errors = 0
    
    for i in range(0, len(items), batch_size):
        batch = items[i:i + batch_size]
        for item_data in batch:
            key = item_data.get("key") or item_data.get("KEY") or item_data.get("name")
            value = item_data.get("value") or item_data.get("VALUE") or item_data.get("v") or item_data.get("content")
            
            if not key or value is None:
                errors += 1
                continue
            
            try:
                add_context_item(
                    project_id=item_data.get("project_id") or project_id,
                    key=str(key),
                    value=str(value),
                    item_type=item_data.get("type") or item_data.get("item_type") or "note",
                    state=item_data.get("state") or "active",
                    tags=item_data.get("tags") or [],
                    sources=item_data.get("sources") or [],
                    stale_after=item_data.get("stale_after"),
                    confidence=item_data.get("confidence", 1.0),
                )
                added += 1
            except Exception:
                errors += 1
    
    return {"added": added, "errors": errors}


def get_all_items(
    project_id: str | None = None,
    state: str | None = None,
    item_type: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Get all items with optional filters (for backup/export)."""
    sql = "SELECT * FROM context_items WHERE 1=1"
    params = []
    
    if project_id is not None:
        sql += " AND project_id = ?"
        params.append(project_id)
    if state is not None:
        sql += " AND state = ?"
        params.append(state)
    if item_type is not None:
        sql += " AND type = ?"
        params.append(item_type)
    
    sql += " ORDER BY created_at DESC"
    if limit is not None:
        sql += f" LIMIT {limit}"
    
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    
    results = []
    for row in rows:
        r = dict(row)
        r["tags"] = json.loads(r["tags"]) if r["tags"] else []
        r["sources"] = json.loads(r["sources"]) if r["sources"] else []
        results.append(r)
    
    return results
