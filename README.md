# NeuralClaw

**Local Context OS for AI Agents**

[![PyPI Version](https://img.shields.io/pypi/v/neuralclaw.svg)](https://pypi.org/project/neuralclaw/)
[![Python](https://img.shields.io/pypi/pyversions/neuralclaw.svg)](https://pypi.org/project/neuralclaw/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Tests](https://github.com/maxsarlija/neuralclaw/actions/workflows/test.yml/badge.svg)](https://github.com/maxsarlija/neuralclaw/actions/workflows/test.yml)

---

NeuralClaw is a **local-first context management system** for AI agents. It organizes your projects, memories, variables, errors, decisions, and communication preferences — then delivers exactly the context each AI needs, formatted for their adapter.

**It does not train models. It does not replace ChatGPT, Claude, or OpenClaw. It sits in the middle as a context layer.**

---

## Installation

Choose the method that fits your setup:

### Via Git Clone

```bash
# Clone the repository
git clone https://github.com/maxsarlija/neuralclaw.git
cd neuralclaw

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install with all extras
pip install -e ".[full]"

# Or minimal installation
pip install -e .
```

### Via pipx (recommended for global install)

```bash
pipx install .
```

### Via pip

```bash
pip install neuralclaw
```

---

## First Run Setup

On first run, NeuralClaw provides an **interactive setup wizard**:

```bash
neuralclaw init
```

The wizard guides you through 4 steps:

```
┌─────────────────────────────────────────────────────────┐
│           🤖 NeuralClaw First Run Setup                 │
├─────────────────────────────────────────────────────────┤
│  Step 1: System Initialization                         │
│           → Creates config, database, vault            │
│                                                         │
│  Step 2: Create Your First Project                      │
│           → Name and description                        │
│                                                         │
│  Step 3: AI Adapter Selection                          │
│           → OpenClaw, Claude, ChatGPT                  │
│                                                         │
│  Step 4: Ollama Integration (Optional)                 │
│           → Enable semantic search                     │
│                                                         │
│                    ✅ Setup Complete!                   │
└─────────────────────────────────────────────────────────┘
```

Use `--yes` or `-y` flag for non-interactive/automated setup:

```bash
neuralclaw init -y
```

---

## Quick Start

Add your first context item:

```bash
neuralclaw add "DATABASE_URL=postgres://localhost/mydb" --type variable --tags prod,database
neuralclaw add "decision: use Redis for session cache" --project myapp --tags architecture
neuralclaw add "Error: timeout on /api/auth" --type error --tags auth,prod
```

Export context for any AI agent:

```bash
neuralclaw context --project myapp --task "implement login" --adapter openclaw
neuralclaw context --project myapp --task "code review" --adapter claude
neuralclaw context --project myapp --task "write tests" --adapter chatgpt
```

---

## Why NeuralClaw?

When working with multiple AI agents, each needs different context. Sending everything to everyone is expensive. Sending nothing means they start from scratch.

NeuralClaw solves this by:

- **Centralizing** project context, decisions, and variables
- **Encrypting** secrets (API keys, tokens) safely in a local vault
- **Routing** the right context to the right agent via adapters
- **Staying local** — no cloud, no sync, no external dependencies

---

## Core Concepts

### Projects

Projects group context items together:

```bash
neuralclaw project create "backend-api"
neuralclaw project list
neuralclaw project status "backend-api"
neuralclaw project archive "old-project"
```

### Context Items

Every piece of information stored is a **context item** with:

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

Encrypted secret storage — values encrypted with Fernet, never exposed unless requested:

```bash
neuralclaw vault set OPENAI_API_KEY "sk-..."
neuralclaw vault list
neuralclaw vault get OPENAI_API_KEY --reveal
neuralclaw vault delete OLD_API_KEY
```

---

## Commands Overview

```
init           Initialize NeuralClaw (interactive wizard)
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
│   └── ui/
│       ├── tui.py            # Text User Interface
│       └── dashboard.py      # Web dashboard
├── tests/                   # 160 tests (all passing)
├── brain/                   # Decision log
├── SPEC.md                  # Design specification
└── CHANGELOG.md
```

### Database

SQLite with 10+ tables: projects, context_items, context_links, errors, decisions, usage_logs, model_profiles, fresh_apple, vault_entries, schema_version, context_fts, embeddings_cache.

---

## Adapters

Adapters define how context is formatted for each AI system:

| Adapter | Tokens | Variables | Style |
|---------|--------|-----------|-------|
| **openclaw** | 200k | revealed | direct |
| **chatgpt** | 128k | hidden | conversational |
| **claude** | 200k | hidden | technical |

---

## Security

- **Fernet symmetric encryption** for vault secrets
- Key stored at `~/.config/neuralclaw/vault.key` (mode 0600)
- Values encrypted; names stored as plaintext
- Graceful degradation: wrong key returns `None`
- **Local-only** — no cloud sync, all data stays on your machine

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.11+ |
| CLI | [Typer](https://typer.tiangolo.com/) + [Rich](https://github.com/Textualize/rich) |
| Database | SQLite (local) |
| Encryption | [cryptography](https://cryptography.io/) (Fernet) |
| Search | FTS5 Full-Text Search |
| Embeddings | [Ollama](https://ollama.ai/) (optional) |
| API | FastAPI (optional) |
| UI | Rich-based TUI |

---

## Version History

| Version | Date | Status |
|---------|------|--------|
| 0.4.1 | 2026-04-27 | Current — Interactive wizard, README updates |
| 0.4.0 | 2026-04-26 | Ollama embeddings, Fresh & Doctor |
| 0.3.0 | 2026-04-26 | Plugin system, Train Room, Playroom |
| 0.2.0 | 2026-04-26 | FreshApple snapshots, health checks |
| 0.1.0 | 2026-04-26 | MVP — init, add, search, vault, context |

---

## Contributing

```bash
git clone https://github.com/maxsarlija/neuralclaw.git
cd neuralclaw
python3 -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
python -m pytest tests/ -v
```

---

## License

MIT License — see [LICENSE](LICENSE) file.

---

*NeuralClaw: Give your AI agents exactly the context they need, nothing more.*