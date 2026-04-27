# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-04-26

### Added

- `neuralclaw init` — Initialize config, database, and encrypted vault
- `neuralclaw add` — Add context items with key=value format, type, tags, state, confidence
- `neuralclaw search` — Search context items with filters (project, state, type, tags, query)
- `neuralclaw context` — Export context as JSON for AI agents (openclaw, chatgpt, claude adapters)
- `neuralclaw project create/list/archive/delete/status` — Project management
- `neuralclaw vault set/get/list/delete/status` — Encrypted secrets management
- SQLite database with full schema (8 tables, FTS5, triggers)
- Vault encryption using Fernet (cryptography)
- 3 model adapters: openclaw.yaml, chatgpt.yaml, claude.yaml
- Context states: active, stale, deprecated, archived, conflicting, verified, unknown, old_school
- Context types: note, decision, error, variable, preference
- Config directory: `~/.config/neuralclaw/` (Linux/macOS), `%APPDATA%/` (Windows)
- Brain log placeholder structure

### Technical Details

- Python 3.11+ with Typer + Rich CLI
- SQLite local database (no cloud dependency)
- Fernet symmetric encryption for vault secrets
- Keyword search (SQL LIKE) — semantic search planned for v0.2
- Full-text search (FTS5) virtual table with triggers for future use
- Context Bridge output format compatible with OpenClaw, ChatGPT, Claude

### Architecture

```
neuralclaw/
├── src/neuralclaw/
│   ├── core/           # Business logic
│   ├── db/             # SQLite schema + connection
│   ├── adapters/       # YAML configs per LLM
│   └── cli/            # CLI commands
├── tests/              # Test suite
├── brain/             # Decision log / version history
└── SPEC.md            # Full design specification
```

---

## Roadmap

### [0.2.0] — Fresh & Doctor
- `neuralclaw fresh` — FreshApple auto-generation with TTL
- `neuralclaw doctor` — Health checks (stale items, conflicts, usage logs)
- Stale detection with configurable TTL
- Conflict detection for context items

### [0.3.0] — Integración IA
- Plugin system with entry points
- Train Room — communication profile generation from samples
- Playroom — prompt testing across adapters

### [0.4.0] — Búsqueda Avanzada
- FTS5 keyword search integration
- Ollama embeddings for semantic search (optional, feature flag)
- Ranking by relevance score

### [0.5.0] — UI
- TUI with Rich
- Optional FastAPI web interface
- Dashboard

---

## [Unreleased] — Future Ideas

- `neuralclaw sync` — Sync context across multiple agents/nodes
- `neuralclaw diff` — Compare context states between timestamps
- `neuralclaw export` — Export full project context as markdown/json
- `neuralclaw import` — Import from other formats (Notion, Obsidian, etc.)
- Web UI with FastAPI
- Language-specific adapters (local models, etc.)
- Context versioning with `brain/` diff history
