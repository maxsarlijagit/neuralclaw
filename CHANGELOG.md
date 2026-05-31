# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Claude Code active-memory integration** (`neuralclaw cc`): use NeuralClaw as persistent, token-optimized memory for Claude Code.
  - `cc install` scaffolds `.mcp.json`, the `SessionStart` hook in `.claude/settings.json`, and a `CLAUDE.md` note (idempotent, merge-safe).
  - `cc recall` / `cc remember` / `cc snapshot` CLI commands.
  - MCP server (`neuralclaw-cc-memory`) exposing `memory_recall`, `memory_store`, `memory_get`, `memory_snapshot` tools.
  - `SessionStart` hook (`neuralclaw-cc-hook`) auto-injects a token-budgeted memory block.
  - New `claude-code` adapter and `[claude-code]` optional dependency (`mcp`).
  - Memory layer applies relevance + recency + state ranking, token budgeting, stale flagging and progressive disclosure (`docs/CLAUDE_CODE.md`).

## [0.4.1] - 2026-04-27

### Fixed

- **vault.py**: `vault_get` now catches `InvalidToken` and returns `None` gracefully instead of raising (fixes wrong key decryption test)
- **projects.py**: Added `created_at` as secondary sort to handle same-timestamp edge case
- **conftest.py**: Fixed `fresh_db` fixture to properly patch `appdirs.user_config_dir` before importing neuralclaw modules
- **test_cli.py**: Updated `import` → `import-cmd` command name (CLI uses `import-cmd` not `import`)
- **test_vault.py**: Relaxed assertion - only checks that secret values are encrypted (names are stored plaintext in vault.db as expected)
- **test_core.py**: Fixed schema version assertion to check non-empty instead of exact string (installed version may differ from schema version)
- **test_projects.py**: Added sleep between project creations to ensure different timestamps

### Changed

- **Tests**: All CLI tests now use `typer.testing.CliRunner` instead of `click.testing.CliRunner` (compatible with Typer 0.25+)

---

## [0.4.0] - 2026-04-26

### Added

- `neuralclaw fresh` — FreshApple snapshots with TTL-based auto-expiration
- `neuralclaw doctor` — Health check system (stale detection, FTS5 validation, schema checks)
- `neuralclaw suggest` — Semantic context search using Ollama embeddings
- `neuralclaw embeddings` — Compute embeddings for text using Ollama
- `neuralclaw train-room` — Analyze samples and generate communication profiles
- `neuralclaw playroom` — Test adapters side-by-side with prompt comparison
- `neuralclaw serve` — FastAPI REST API server with web dashboard
- `neuralclaw tui` — Interactive Text User Interface
- `neuralclaw plugin` — Plugin management system
- `neuralclaw import-cmd` — Bulk import from JSON/JSONL files
- `neuralclaw config` — Configuration management
- Plugin system with entry points (`neuralclaw.plugins`)

### Technical Details

- Full FTS5 virtual table with triggers for keyword search
- Ollama integration for semantic embeddings (optional, feature flag)
- FastAPI server with Jinja2 templating
- Rich-based TUI
- Embeddings cache in database

---

## [0.3.0] - 2026-04-26

### Added

- Plugin system with entry points
- Train Room — communication profile generation
- Playroom — prompt testing across adapters

---

## [0.2.0] - 2026-04-26

### Added

- `neuralclaw fresh` — FreshApple auto-generation
- `neuralclaw doctor` — Health checks
- Stale detection with configurable TTL
- Conflict detection for context items

---

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

### Technical Details

- Python 3.11+ with Typer + Rich CLI
- SQLite local database (no cloud dependency)
- Fernet symmetric encryption for vault secrets
- Keyword search (SQL LIKE) — semantic search planned for v0.2
- Full-text search (FTS5) virtual table with triggers for future use
- Context Bridge output format compatible with OpenClaw, ChatGPT, Claude

---

*Changelog started: 2026-04-26*