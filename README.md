# NeuralClaw

**Local Context OS for AI Agents**

[![PyPI Version](https://img.shields.io/pypi/v/neuralclaw.svg)](https://pypi.org/project/neuralclaw/)
[![Python](https://img.shields.io/pypi/pyversions/neuralclaw.svg)](https://pypi.org/project/neuralclaw/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/maxsarlija/neuralclaw/blob/main/LICENSE)
[![Tests](https://github.com/maxsarlija/neuralclaw/actions/workflows/test.yml/badge.svg)](https://github.com/maxsarlija/neuralclaw/actions/workflows/test.yml)

---

NeuralClaw is a **local-first context management system** for AI agents. It organizes your projects, memories, variables, errors, decisions, and communication preferences — then delivers exactly the context each AI needs, formatted for their adapter.

**It does not train models. It does not replace ChatGPT, Claude, or OpenClaw. It sits in the middle as a context layer.**

---

## Why NeuralClaw?

When you're working with multiple AI agents across different tasks, each one needs different context. Sending everything to every agent is expensive and slow. Sending nothing means they start from scratch.

NeuralClaw solves this by:

- **Centralizing** project context, decisions, and variables in one place
- **Encrypting** secrets (API keys, tokens) safely in a local vault
- **Routing** the right context to the right agent via adapters
- **Staying local** — no cloud, no sync, no dependencies

---

## Quick Start

### Installation

```bash
# Using pipx (recommended)
pipx install .

# Or using pip with venv
python3 -m venv venv
source venv/bin/activate
pip install -e .
```

### Initialize

```bash
neuralclaw init
```

This creates:
- `~/.config/neuralclaw/` — config directory
- `~/.config/neuralclaw/neuralclaw.db` — SQLite database
- `~/.config/neuralclaw/vault.key` — encryption key
- `~/.config/neuralclaw/vault/vault.db` — encrypted secrets store

### Add Context

```bash
# Add a variable
neuralclaw add "DATABASE_URL=postgres://localhost/mydb" --type variable --tags prod,database

# Add a decision
neuralclaw add "decision: use Redis for session cache" --project myapp --tags architecture

# Add an error tracking item
neuralclaw add "Error: timeout on /api/auth endpoint" --type error --tags auth,prod
```

### Export Context for an Agent

```bash
# For OpenClaw agents
neuralclaw context --project myapp --task "implement login" --adapter openclaw

# For Claude
neuralclaw context --project myapp --task "code review" --adapter claude

# For ChatGPT
neuralclaw context --project myapp --task "write tests" --adapter chatgpt
```

---

## Core Concepts

### Projects

Projects group context items together. Each project has its own namespace for variables, decisions, and errors.

```bash
neuralclaw project create "backend-api"
neuralclaw project list
neuralclaw project status "backend-api"
neuralclaw project archive "old-project"
```

### Context Items

Everything NeuralClaw stores is a **context item** with:

| Field | Description |
|-------|-------------|
| `key` | Identifier (e.g., `DATABASE_URL`) |
| `value` | The actual data |
| `type` | `note`, `variable`, `decision`, `error`, `preference` |
| `state` | `active`, `stale`, `deprecated`, `archived`, `verified` |
| `tags` | Labels for filtering |
| `project` | Associated project |
| `confidence` | Trust level (0-1) |

### States

Context items have lifecycle states:

| State | Include in exports? | Action |
|-------|---------------------|--------|
| `active` | ✅ By default | Use normally |
| `verified` | ✅ High priority | High confidence |
| `stale` | ⚠️ With warning | Verify before using |
| `conflicting` | ⚠️ With warning | Escalate to agent |
| `deprecated` | ❌ Unless requested | Skip |
| `archived` | ❌ Unless requested | Skip |
| `old_school` | ❌ On-demand only | Load when needed |

### Vault

The vault stores **encrypted secrets** — API keys, tokens, passwords. Values are encrypted with Fernet (symmetric encryption) and never exposed unless explicitly requested.

```bash
neuralclaw vault set OPENAI_API_KEY "sk-..."
neuralclaw vault list
neuralclaw vault get OPENAI_API_KEY --reveal
neuralclaw vault delete OLD_API_KEY
```

---

## Commands Overview

```
init           Initialize NeuralClaw: config, database, vault
add            Add a context item (key=value format)
search         Search context items with filters
context        Export context as JSON for an AI agent

project        Manage projects (create, list, archive, delete, status)
vault          Manage encrypted secrets (set, get, list, delete)
plugin         Manage plugins

fresh          Generate FreshApple snapshots (TTL-based context)
doctor         Run health checks (stale detection, schema validation)
suggest        Semantic search using Ollama embeddings
embeddings     Compute embeddings for text

train-room     Generate communication profiles from samples
playroom       Test adapters side-by-side with prompt comparison

tui            Launch interactive Text User Interface
serve          Start FastAPI REST API server with web dashboard
config         Manage NeuralClaw configuration

import-cmd     Bulk import from JSON/JSONL files
```

---

## Architecture

```
neuralclaw/
├── src/neuralclaw/
│   ├── cli/main.py          # CLI entry point (Typer + Rich)
│   ├── core/
│   │   ├── context.py       # CRUD for context items
│   │   ├── projects.py      # Project management
│   │   ├── vault.py         # Encrypted secrets (Fernet)
│   │   ├── search.py        # Smart search with FTS5
│   │   ├── bridge.py        # Context export per adapter
│   │   ├── embeddings.py    # Ollama integration
│   │   ├── fresh.py         # FreshApple snapshots
│   │   ├── doctor.py        # Health check system
│   │   ├── train_room.py    # Communication profiles
│   │   └── playroom.py      # Adapter testing
│   ├── db/
│   │   └── connection.py    # SQLite + migrations
│   ├── adapters/            # YAML configs per LLM
│   │   ├── openclaw.yaml
│   │   ├── chatgpt.yaml
│   │   └── claude.yaml
│   ├── api/server.py        # FastAPI REST API
│   └── ui/tui.py            # Text User Interface
├── tests/                   # 160 tests (all passing)
├── brain/                   # Decision log
├── SPEC.md                  # Design specification
└── CHANGELOG.md
```

### Database Schema

NeuralClaw uses SQLite with 10+ tables:

- `projects` — project metadata
- `context_items` — key-value context with types and states
- `context_links` — relationships (supersedes, contradicts)
- `errors` — error log per project
- `decisions` — decision history with rationale
- `usage_logs` — audit trail
- `model_profiles` — communication profiles (Train Room)
- `fresh_apple` — TTL-based snapshots
- `vault_entries` — encrypted secret metadata
- `schema_version` — migration tracking
- `context_fts` — FTS5 full-text search virtual table
- `embeddings_cache` — cached Ollama embeddings

---

## Security

### Vault Encryption

The vault uses **Fernet symmetric encryption** (cryptography library):

- Key stored at `~/.config/neuralclaw/vault.key` (mode 0600)
- Values encrypted before storage
- Name/metadata stored in plaintext; values never exposed
- Graceful degradation: wrong key returns `None` instead of crashing

### Local-Only

- No cloud sync, no external dependencies
- All data stays on your machine
- Gitignored vault directory: `~/.config/neuralclaw/vault/`

---

## Adapters

Adapters define how context is formatted for each AI system:

### OpenClaw

```yaml
max_tokens: 200000
reveal_vars: true
style: direct
supports_system: true
supports_functions: false
```

### ChatGPT

```yaml
max_tokens: 128000
reveal_vars: false
style: conversational
supports_system: true
supports_functions: true
```

### Claude

```yaml
max_tokens: 200000
reveal_vars: false
style: technical
supports_system: true
supports_functions: true
```

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.11+ |
| CLI | [Typer](https://typer.tiangolo.com/) + [Rich](https://github.com/Textualize/rich) |
| Database | SQLite (local, no cloud) |
| Encryption | [cryptography](https://cryptography.io/) (Fernet) |
| Search | FTS5 (Full-Text Search) |
| Embeddings | [Ollama](https://ollama.ai/) (optional) |
| API | FastAPI (optional server mode) |
| UI | Rich-based TUI |

---

## Version History

| Version | Date | Status |
|---------|------|--------|
| 0.4.1 | 2026-04-27 | Current — Test suite fixes |
| 0.4.0 | 2026-04-26 | Ollama embeddings, Fresh & Doctor |
| 0.3.0 | 2026-04-26 | Plugin system, Train Room, Playroom |
| 0.2.0 | 2026-04-26 | FreshApple snapshots, health checks |
| 0.1.0 | 2026-04-26 | MVP — init, add, search, vault, context |

---

## Contributing

Contributions welcome. Areas of interest:

- More adapters (LocalAI, LM Studio, etc.)
- TUI improvements
- Web UI enhancements
- Performance optimizations

```bash
# Development setup
git clone https://github.com/maxsarlija/neuralclaw.git
cd neuralclaw
python3 -m venv venv
source venv/bin/activate
pip install -e ".[dev]"

# Run tests
python -m pytest tests/ -v
```

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

*NeuralClaw: Give your AI agents exactly the context they need, nothing more.*