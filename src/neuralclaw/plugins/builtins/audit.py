"""Audit plugin — logs every context access to a local log file."""

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import appdirs

logger = logging.getLogger(__name__)


def _get_audit_log_path() -> Path:
    """Get the audit log file path in config dir."""
    config_dir = Path(appdirs.user_config_dir("neuralclaw"))
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "audit.log"


def _audit_log(action: str, **kwargs: Any) -> None:
    """Append an audit record to the audit log."""
    audit_log = _get_audit_log_path()
    entry = {
        "timestamp": datetime.now().isoformat(),
        "unixtime": int(time.time()),
        "action": action,
        **kwargs,
    }
    try:
        with open(audit_log, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as exc:
        logger.warning("Audit log write failed: %s", exc)


def hooks() -> dict[str, Any]:
    """Return the audit plugin hooks."""
    return {
        "on_context_search": _on_context_search,
        "on_context_export": _on_context_export,
        "on_doctor_check": _on_doctor_check,
    }


def _on_context_search(
    query: str | None,
    project_id: str | None,
    results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Log every context search."""
    _audit_log(
        "context_search",
        query=query,
        project_id=project_id,
        result_count=len(results),
    )
    return results


def _on_context_export(export_data: dict[str, Any]) -> dict[str, Any]:
    """Log every context export."""
    _audit_log(
        "context_export",
        task=export_data.get("task", ""),
        adapter=export_data.get("metadata", {}).get("adapter", "unknown"),
        item_count=export_data.get("metadata", {}).get("total_items", 0),
    )
    return export_data


def _on_doctor_check() -> list[dict[str, str]]:
    """Add audit system health check."""
    checks: list[dict[str, str]] = []
    audit_log = _get_audit_log_path()
    if audit_log.exists():
        try:
            with open(audit_log, "a") as f:
                f.write("")
            checks.append({
                "check": "audit_log",
                "status": "ok",
                "message": f"Audit log writable at {audit_log}",
            })
        except Exception as exc:
            checks.append({
                "check": "audit_log",
                "status": "warn",
                "message": f"Audit log not writable: {exc}",
            })
    else:
        checks.append({
            "check": "audit_log",
            "status": "warn",
            "message": "Audit log not initialized yet",
        })
    return checks
