"""FreshApple - Markdown snapshots of active project context."""

import uuid
import time
import json
from typing import Any

from neuralclaw.db.connection import get_connection, get_vault_key_path, db_exists
from neuralclaw.core.context import search_context


def generate_fresh_apple(project_id: str | None = None, project_name: str | None = None) -> str:
    """Generate a FreshApple markdown snapshot for a project or global context.

    FreshApple = markdown snapshot of active context (projects, next steps, risks,
    recent errors, key context).
    """
    now = int(time.time())
    lines = [
        "# 🍎 FreshApple — Active Context Snapshot",
        f"_Generated: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(now))}_",
        "",
    ]

    # Projects summary
    with get_connection() as conn:
        projects = conn.execute(
            "SELECT id, name, status, description, updated_at FROM projects ORDER BY updated_at DESC"
        ).fetchall()

    if projects:
        lines.append("## 📁 Projects")
        for p in projects:
            status_emoji = "🟢" if p["status"] == "active" else "📦" if p["status"] == "archived" else "🟡"
            age_days = (now - p["updated_at"]) / 86400
            age_str = f" ({age_days:.1f}d ago)" if age_days > 1 else "(today)"
            lines.append(f"- {status_emoji} **{p['name']}** — {p['status']}{age_str}")
            if p["description"]:
                lines.append(f"  {p['description'][:100]}")
        lines.append("")

    # Context items
    if project_id:
        # Single project context
        project_name_str = project_name or project_id
        lines.append(f"## 🧠 Context: {project_name_str}")
        items = _get_project_context_items(project_id, now)
        lines.extend(items)
    else:
        # Global context — show per-project summaries
        lines.append("## 🧠 Global Context")
        for p in projects:
            if p["status"] == "archived":
                continue
            lines.append(f"### {p['name']}")
            items = _get_project_context_items(p["id"], now)
            if not items:
                lines.append("_No active items_")
            lines.extend(items)
            lines.append("")

    # Recent errors
    with get_connection() as conn:
        recent_errors = conn.execute("""
            SELECT error_type, message, created_at, project_id
            FROM errors
            WHERE resolved = 0
            ORDER BY created_at DESC
            LIMIT 10
        """).fetchall()

    if recent_errors:
        lines.append("## 🚨 Recent Errors (unresolved)")
        for e in recent_errors:
            age = _age_str(now - e["created_at"])
            msg_short = e["message"][:80] + ("..." if len(e["message"]) > 80 else "")
            lines.append(f"- `{e['error_type']}` {msg_short} — {age}")
        lines.append("")

    # Conflicting items
    with get_connection() as conn:
        conflicts = conn.execute("""
            SELECT key, value, project_id FROM context_items
            WHERE state = 'conflicting'
            ORDER BY updated_at DESC
            LIMIT 20
        """).fetchall()

    if conflicts:
        lines.append("## ⚠️ Conflicting Items")
        for c in conflicts:
            pname = conn.execute(
                "SELECT name FROM projects WHERE id = ?", (c["project_id"],)
            ).fetchone()
            pstr = f" [{pname['name']}]" if pname else ""
            lines.append(f"- **{c['key']}**{pstr}: `{c['value'][:60]}`")
        lines.append("")

    # Stale items count
    with get_connection() as conn:
        stale_count = conn.execute("""
            SELECT COUNT(*) as cnt FROM context_items WHERE state = 'stale'
        """).fetchone()
        stale_total = stale_count["cnt"] if stale_count else 0

    if stale_total > 0:
        lines.append(f"## ⏳ Stale Items: {stale_total} total")
        lines.append("")

    # Vault status
    vault_key_path = get_vault_key_path()
    if vault_key_path.exists():
        with get_connection() as conn:
            vault_count = conn.execute(
                "SELECT COUNT(*) as cnt FROM vault_entries"
            ).fetchone()
            vault_total = vault_count["cnt"] if vault_count else 0
        lines.append(f"## 🔐 Vault: {vault_total} secrets stored")
        lines.append("")
    else:
        lines.append("## 🔐 Vault: NOT INITIALIZED")
        lines.append("")

    lines.append("_End of FreshApple_")
    return "\n".join(lines)


def _get_project_context_items(project_id: str, now: int) -> list[str]:
    """Get context items formatted for a project."""
    lines = []
    items = search_context(project_id=project_id, state=None, limit=100)

    # Group by type
    by_type: dict[str, list] = {}
    for item in items:
        t = item["type"]
        by_type.setdefault(t, []).append(item)

    type_labels = {
        "decision": "Decisions",
        "error": "Errors",
        "variable": "Variables",
        "preference": "Preferences",
        "note": "Notes",
    }

    for t, label in type_labels.items():
        if t in by_type:
            lines.append(f"**{label}:**")
            for item in by_type[t][:10]:
                stale_flag = ""
                if item.get("stale_after") and item["stale_after"] < now:
                    stale_flag = " ⏳STALE"
                confidence_str = f" [{item['confidence']:.0%}]" if item.get("confidence", 1.0) < 1.0 else ""
                val_short = item["value"][:60] + ("..." if len(item["value"]) > 60 else "")
                lines.append(f"- `{item['key']}` = {val_short}{stale_flag}{confidence_str}")
            lines.append("")

    # Ungrouped notes
    if "note" in by_type and len(by_type["note"]) > 10:
        lines.append(f"_(+{len(by_type['note']) - 10} more notes)_")

    return lines


def _age_str(seconds: int) -> str:
    """Format age in human-readable form."""
    if seconds < 60:
        return f"{seconds}s ago"
    if seconds < 3600:
        return f"{seconds // 60}m ago"
    if seconds < 86400:
        return f"{seconds // 3600}h ago"
    return f"{seconds // 86400}d ago"


def save_fresh_apple(project_id: str | None, content: str, auto_refresh: bool = True) -> str | None:
    """Save a FreshApple snapshot to the database.

    Returns the fresh_id, or None if project_id is None (global context).
    Global FreshApple is generated fresh each time but not persisted.
    """
    if project_id is None:
        # Global context: generate fresh each time, don't persist
        return None

    fresh_id = str(uuid.uuid4())
    now = int(time.time())

    with get_connection() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO fresh_apple
            (id, project_id, content, generated_at, auto_refresh)
            VALUES (
                COALESCE((SELECT id FROM fresh_apple WHERE project_id = ?), ?),
                ?, ?, ?, ?
            )
        """, (project_id, fresh_id, project_id, content, now, 1 if auto_refresh else 0))

    return fresh_id


def get_fresh_apple(project_id: str | None = None) -> dict[str, Any] | None:
    """Get the stored FreshApple for a project (or None if doesn't exist)."""
    with get_connection() as conn:
        if project_id:
            row = conn.execute(
                "SELECT * FROM fresh_apple WHERE project_id = ?", (project_id,)
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM fresh_apple ORDER BY generated_at DESC LIMIT 1"
            ).fetchone()

    if not row:
        return None

    r = dict(row)
    return r


def list_fresh_apples() -> list[dict[str, Any]]:
    """List all stored FreshApples with project info."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT fa.*, p.name as project_name
            FROM fresh_apple fa
            LEFT JOIN projects p ON fa.project_id = p.id
            ORDER BY fa.generated_at DESC
        """).fetchall()

    return [dict(row) for row in rows]


def is_fresh(project_id: str, ttl_seconds: int = 3600) -> bool:
    """Check if a FreshApple is still fresh (within TTL)."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT generated_at FROM fresh_apple WHERE project_id = ?", (project_id,)
        ).fetchone()

    if not row:
        return False

    now = int(time.time())
    return (now - row["generated_at"]) < ttl_seconds
