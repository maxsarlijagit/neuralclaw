"""NeuralClaw Doctor — Health checks for the NeuralClaw system."""

import time
import sys
from typing import NamedTuple

from neuralclaw.db.connection import (
    get_connection, db_exists, get_schema_version,
    get_vault_key_path, get_db_path, get_config_dir
)
from neuralclaw.core.fresh import list_fresh_apples


class CheckResult(NamedTuple):
    status: str  # "pass", "warn", "fail"
    label: str
    detail: str = ""


def run_doctor_checks() -> tuple[list[CheckResult], int, int]:
    """Run all doctor health checks. Returns (results, pass_count, total_count)."""
    results: list[CheckResult] = []
    now = int(time.time())

    # 1. DB accessible + schema correct
    results.append(_check_db(now))

    # 2. Vault.key exists
    results.append(_check_vault_key())

    # 3. FreshApple freshness
    results.append(_check_fresh_apple(now))

    # 4. Stale items without refresh
    results.append(_check_stale_items(now))

    # 5. Conflicts unresolved
    results.append(_check_conflicts(now))

    # 6. usage_logs empty for 30+ days
    results.append(_check_usage_logs(now))

    pass_count = sum(1 for r in results if r.status == "pass")
    total = len(results)
    return results, pass_count, total


def _check_db(now: int) -> CheckResult:
    """Check DB accessibility and schema."""
    if not db_exists():
        return CheckResult("fail", "DB", "Database does not exist at ~/.config/neuralclaw/")

    try:
        version = get_schema_version()
        if version is None:
            return CheckResult("fail", "DB", "Schema version not found in DB")
        return CheckResult("pass", "DB", f"OK (schema v{version})")
    except Exception as e:
        return CheckResult("fail", "DB", f"Cannot connect: {e}")


def _check_vault_key() -> CheckResult:
    """Check if vault.key exists."""
    key_path = get_vault_key_path()
    if key_path.exists():
        return CheckResult("pass", "Vault Key", "vault.key exists")
    else:
        return CheckResult("fail", "Vault Key", "vault.key NOT found — run 'neuralclaw init'")


def _check_fresh_apple(now: int) -> CheckResult:
    """Check FreshApple files for staleness (>7 days old)."""
    if not db_exists():
        return CheckResult("fail", "FreshApple", "DB not available")

    fresh_list = list_fresh_apples()
    if not fresh_list:
        return CheckResult("warn", "FreshApple", "No FreshApple snapshots found")

    stale_count = 0
    fresh_count = 0
    for fa in fresh_list:
        age_seconds = now - fa["generated_at"]
        age_days = age_seconds / 86400
        if age_days > 7:
            stale_count += 1
        else:
            fresh_count += 1

    if stale_count > 0 and fresh_count > 0:
        return CheckResult(
            "warn", "FreshApple",
            f"{stale_count} snapshot(s) sin refresh en >7 días, {fresh_count} fresh"
        )
    elif stale_count > 0:
        return CheckResult(
            "warn", "FreshApple",
            f"{stale_count} project(s) sin refresh en >7 días"
        )
    else:
        return CheckResult("pass", "FreshApple", f"All {fresh_count} snapshots fresh (<7 days)")


def _check_stale_items(now: int) -> CheckResult:
    """Check for items that are stale (stale_after timestamp passed)."""
    if not db_exists():
        return CheckResult("fail", "Stale Items", "DB not available")

    with get_connection() as conn:
        # Items past their stale_after timestamp but not marked stale
        overdue = conn.execute("""
            SELECT COUNT(*) as cnt FROM context_items
            WHERE state NOT IN ('stale', 'archived', 'deprecated')
            AND stale_after IS NOT NULL
            AND stale_after < ?
        """, (now,)).fetchone()

        # Items already marked stale
        stale_marked = conn.execute("""
            SELECT COUNT(*) as cnt FROM context_items WHERE state = 'stale'
        """).fetchone()

    overdue_cnt = overdue["cnt"] if overdue else 0
    stale_cnt = stale_marked["cnt"] if stale_marked else 0

    if overdue_cnt == 0 and stale_cnt == 0:
        return CheckResult("pass", "Stale Items", "No stale items")
    elif overdue_cnt > 0:
        return CheckResult(
            "warn", "Stale Items",
            f"{overdue_cnt} item(s) overdue (TTL passed, not flagged), {stale_cnt} already marked stale"
        )
    else:
        return CheckResult("pass", "Stale Items", f"{stale_cnt} marked stale")


def _check_conflicts(now: int) -> CheckResult:
    """Check for unresolved conflicting context items."""
    if not db_exists():
        return CheckResult("fail", "Conflicts", "DB not available")

    with get_connection() as conn:
        rows = conn.execute("""
            SELECT key, project_id, COUNT(*) as cnt
            FROM context_items
            WHERE state = 'conflicting'
            GROUP BY key, project_id
        """).fetchall()

    conflict_groups = len(rows)
    total_conflicts = sum(r["cnt"] for r in rows)

    if conflict_groups == 0:
        return CheckResult("pass", "Conflicts", "No conflicting items")

    return CheckResult(
        "fail", "Conflicts",
        f"{conflict_groups} conflicting key(s), {total_conflicts} total conflicting items"
    )


def _check_usage_logs(now: int) -> CheckResult:
    """Check if usage_logs is empty for 30+ days."""
    if not db_exists():
        return CheckResult("fail", "Usage Logs", "DB not available")

    with get_connection() as conn:
        row = conn.execute("""
            SELECT MAX(created_at) as last_used FROM usage_logs
        """).fetchone()

    if not row or row["last_used"] is None:
        return CheckResult("warn", "Usage Logs", "No usage logs recorded (never used?)")

    age_seconds = now - row["last_used"]
    age_days = age_seconds / 86400

    if age_days > 30:
        return CheckResult(
            "warn", "Usage Logs",
            f"No usage in {age_days:.0f} days (last: {time.strftime('%Y-%m-%d', time.localtime(row['last_used']))})"
        )
    else:
        return CheckResult(
            "pass", "Usage Logs",
            f"Last used {age_days:.1f} days ago"
        )


def print_doctor_report(results: list[CheckResult], pass_count: int, total: int) -> None:
    """Print the doctor report to stdout."""
    status_icon = {"pass": "✅", "warn": "⚠️ ", "fail": "❌"}

    print()
    print("🩺 NeuralClaw Doctor")
    print("─" * 50)

    for r in results:
        icon = status_icon.get(r.status, "•")
        status_str = r.status.upper() if r.status != "pass" else "OK"
        print(f"{icon} {r.label}: {r.detail}")

    print("─" * 50)
    print(f"Status: {pass_count}/{total} checks passed")

    if pass_count < total:
        sys.exit(1)
