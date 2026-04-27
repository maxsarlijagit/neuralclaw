"""Context Bridge - export context for AI agents."""

import json
import time
from pathlib import Path
from typing import Any

import yaml

from neuralclaw.core import vault as vault_module

ADAPTERS_DIR = Path(__file__).parent.parent / "adapters"


def load_adapter(adapter_name: str) -> dict[str, Any]:
    """Load an adapter configuration."""
    adapter_file = ADAPTERS_DIR / f"{adapter_name}.yaml"
    if not adapter_file.exists():
        raise ValueError(f"Adapter '{adapter_name}' not found. Check adapters/ directory.")
    return yaml.safe_load(adapter_file.read_text())


from neuralclaw.core import search as search_module

def build_context_export(
    task: str,
    project_id: str | None = None,
    adapter_name: str = "openclaw",
    include_vars: bool = False,
    query: str | None = None,
    max_tokens: int | None = None,
) -> dict[str, Any]:
    """Build a context export JSON for an AI agent."""
    adapter = load_adapter(adapter_name)

    # Search relevant context (use smart search with keyword method for export)
    items = search_module.search_context_smart(
        query=query,
        project_id=project_id,
        state="active",
        method="keyword",
        limit=200,
    )

    # Sort by relevance_score descending (if available)
    items.sort(key=lambda x: x.get("relevance_score", 1.0), reverse=True)

    # Check for stale items
    now = int(time.time())
    warnings = []
    for item in items:
        if item.get("stale_after") and item["stale_after"] < now:
            warnings.append(f"Item '{item['key']}' may be stale (last updated {item['updated_at']})")
        if item["state"] == "conflicting":
            warnings.append(f"Item '{item['key']}' has conflicting state")

    # Process vault vars
    vault_vars = {}
    if include_vars and adapter.get("reveal_vars", False):
        for item in items:
            if item["type"] == "variable" and item["value"].startswith("{{") and item["value"].endswith("}}"):
                var_name = item["value"][2:-2]
                actual_value = vault_module.vault_get(var_name)
                if actual_value:
                    vault_vars[var_name] = actual_value

    # Apply adapter preferences to format
    context_output = []
    for item in items:
        value = item["value"]
        # Substitute vault vars if revealing
        if vault_vars:
            for var_name, var_value in vault_vars.items():
                if f"{{{{{var_name}}}}}" in value:
                    value = value.replace(f"{{{{{var_name}}}}}", var_value)

        context_output.append({
            "id": item["id"],
            "key": item["key"],
            "value": value,
            "type": item["type"],
            "state": item["state"],
            "tags": item["tags"],
            "confidence": item["confidence"],
            "sources": item["sources"],
            "stale_warning": item.get("stale_after", 0) < now if item.get("stale_after") else False,
        })

    # Token estimate (rough)
    total_chars = sum(len(json.dumps(c)) for c in context_output)
    tokens_estimate = total_chars // 4

    return {
        "task": task,
        "context": context_output,
        "constraints": adapter.get("constraints", []),
        "warnings": warnings,
        "sources": [f"context_items table, project_id={project_id}"],
        "metadata": {
            "project": project_id or "global",
            "total_items": len(context_output),
            "tokens_estimate": tokens_estimate,
            "adapter": adapter_name,
        }
    }


def export_context_json(
    task: str,
    project_id: str | None = None,
    adapter_name: str = "openclaw",
    include_vars: bool = False,
    query: str | None = None,
) -> str:
    """Export context as JSON string."""
    export = build_context_export(
        task=task,
        project_id=project_id,
        adapter_name=adapter_name,
        include_vars=include_vars,
        query=query,
    )
    return json.dumps(export, indent=2, ensure_ascii=False)
