# Architecture

## Overview

NeuralClaw is a local context management system for AI agents. It stores, searches, and exports structured context data with an encrypted vault for secrets.

## Components

```
neuralclaw/
├── src/neuralclaw/
│   ├── __init__.py          # Package init
│   ├── __main__.py          # Entry point
│   ├── logging.py           # Structured logging with Rich
│   ├── cli/
│   │   └── main.py          # Typer CLI application
│   ├── core/
│   │   ├── context.py       # Context item CRUD & search
│   │   ├── projects.py      # Project management
│   │   ├── vault.py        # Encrypted secret storage
│   │   └── bridge.py       # Context export for AI adapters
│   ├── db/
│   │   ├── connection.py    # SQLite connection management
│   │   └── schema.sql      # Database schema
│   └── adapters/           # AI adapter configurations
│       ├── openclaw.yaml
│       ├── chatgpt.yaml
│       └── claude.yaml
├── tests/                   # Test suite
├── docs/                    # Documentation
└── .github/workflows/       # CI/CD pipelines
```

## Database

NeuralClaw uses SQLite as a local database stored at `~/.config/neuralclaw/neuralclaw.db`.

### Schema Modules

| Table | Purpose |
|-------|---------|
| `projects` | Project metadata and status |
| `context_items` | Core key-value context storage |
| `context_links` | Relationships between context items |
| `errors` | Error log with resolution tracking |
| `decisions` | Decision log with rationale |
| `usage_logs` | Audit log of all actions |
| `model_profiles` | Train Room model configurations |
| `fresh_apple` | Auto-refreshed context snapshots |
| `vault_entries` | Encrypted secrets metadata |

### Indexes

- `idx_context_project` — Fast project-scoped queries
- `idx_context_state` — State filtering
- `idx_context_stale` — Stale detection
- `idx_context_type` — Type filtering
- `idx_context_key` — Key lookups
- `idx_errors_project` — Project error queries
- `idx_errors_resolved` — Resolution filtering
- `idx_decisions_project` — Decision queries
- `idx_fresh_project` — FreshApple lookups
- `idx_usage_project` — Usage audit queries
- `idx_usage_created` — Time-based usage queries
- `idx_links_from/to` — Link traversal

### Full-Text Search

FTS5 virtual table (`context_fts`) provides keyword search with triggers keeping it synchronized.

## Vault

The vault stores encrypted secrets using Fernet (AES-128-CBC with HMAC). Keys are stored in `vault.key` and encrypted values in `vault/vault.db`.

## Adapters

Adapters define how context is formatted for different AI systems. Each adapter is a YAML file with:

- `reveal_vars` — Whether to expose secret values
- `constraints` — Formatting constraints
- `format_preference` — Output format hints

## Logging

Structured logging with Rich to:
- Console: Human-readable with colors
- File: `~/.cache/neuralclaw/neuralclaw.log` — Machine-parseable format

Every command logs: action, timestamp, project_id, duration.

## Plugin System

Plugins are entry-points under `neuralclaw.plugins`. Each plugin implements:
- `on_context_add` — Hook when context is added
- `on_context_search` — Hook for search results
- `on_export` — Hook for context export
