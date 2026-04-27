# Plugin Development Guide

## Overview

NeuralClaw supports plugins via entry-points under `neuralclaw.plugins`. Plugins can hook into context operations and exports.

## Creating a Plugin

### 1. Create your plugin package

```bash
mkdir my_plugin
cd my_plugin
```

### 2. Define in pyproject.toml

```toml
[project]
name = "neuralclaw-my-plugin"
version = "0.1.0"

[project.entry-points."neuralclaw.plugins"]
my_plugin = "my_plugin:plugin"
```

### 3. Implement the plugin

```python
"""my_plugin.py — My custom NeuralClaw plugin."""

from typing import Any

def plugin(config: dict[str, Any]) -> dict[str, Any]:
    """Initialize plugin with config."""
    return {
        "name": "my_plugin",
        "hooks": {
            "on_context_add": on_context_add,
            "on_context_search": on_context_search,
            "on_export": on_export,
        },
    }

def on_context_add(item: dict[str, Any]) -> dict[str, Any]:
    """Called when a context item is added."""
    # Modify or enrich the item
    item["tags"] = item.get("tags", []) + ["processed"]
    return item

def on_context_search(results: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
    """Called with search results before returning."""
    # Filter or rank results
    return [r for r in results if r.get("confidence", 1.0) > 0.5]

def on_export(export: dict[str, Any], adapter: str) -> dict[str, Any]:
    """Called before context export."""
    export["metadata"]["plugin"] = "my_plugin"
    return export
```

### 4. Install your plugin

```bash
pip install -e "."
```

## Available Hooks

| Hook | Signature | Description |
|------|-----------|-------------|
| `on_context_add` | `(item) -> item` | Transform/add context item |
| `on_context_search` | `(results, query) -> results` | Filter search results |
| `on_export` | `(export, adapter) -> export` | Modify export output |
| `on_doctor_check` | `(report) -> report` | Add doctor check results |

## Configuration

Plugins receive config from `pyproject.toml` or environment:

```toml
[tool.neuralclaw.plugins.my_plugin]
api_key = "sk-..."
enabled = true
```

## Example: Slack Notification Plugin

```python
"""slack_notify.py — Notify Slack on new context items."""

import os
import requests
from typing import Any

def plugin(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": "slack_notify",
        "hooks": {"on_context_add": notify_slack},
    }

def notify_slack(item: dict[str, Any]) -> dict[str, Any]:
    webhook = os.environ.get("SLACK_WEBHOOK_URL")
    if webhook and item.get("type") == "decision":
        requests.post(webhook, json={
            "text": f"New decision: {item['key']} = {item['value']}"
        })
    return item
```
