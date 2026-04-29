# NeuralClaw — Feature Reference

**Version:** 0.4.1
**PyPI:** `pip install neuralclaw-os`
**Repo:** github.com/maxsarlijagit/neuralclaw

---

## Context Items

### `neuralclaw add` — Add context item
Add a context item with smart type inference.

```bash
neuralclaw add "DATABASE_URL=postgres://localhost/mydb" --project mi-app
neuralclaw add "decision: use Redis for session cache" --tags architecture
neuralclaw add "Error: timeout on /api/auth" --type error --tags prod,auth
neuralclaw add "deploy: run migrate.sh" --type process
```

**Smart inference:** Type auto-detected from content:
- `KEY=value` → type: variable
- `decision:` prefix → type: decision
- `Error:`, `BUG:`, `CRASH:` → type: error
- `TODO:`, `NOTE:`, `FIXME:` → type: note
- `deploy:`, `run:`, `execute:` → type: process
- Free text → type: note

**Flags:** `--project`, `--type`, `--tags`, `--state`, `--stale-after`, `--confidence`, `--interactive`

---

### `neuralclaw search` — Search context
Search items by keyword with filters.

```bash
neuralclaw search database
neuralclaw search "error" --type error --project mi-app
neuralclaw search --interactive  # Interactive mode
neuralclaw search --limit 20 --offset 0
```

**Flags:** `--project`, `--type`, `--state`, `--tags`, `--limit`, `--offset`, `--method`, `--use-fts`, `--json`

---

### `neuralclaw suggest` — Semantic search
Find related context using Ollama embeddings.

```bash
neuralclaw suggest "authentication flow"
neuralclaw suggest "database connection" --project mi-app
```

**Requires:** Ollama running with embeddings model.

---

### `neuralclaw context` — Export for AI agents
Export context as JSON formatted for a specific AI adapter.

```bash
neuralclaw context --project mi-app --task "implement login"
neuralclaw context --project mi-app --adapter claude --include-vars
```

**Adapters:** `openclaw`, `chatgpt`, `claude`
**Flags:** `--task`, `--project`, `--adapter`, `--include-vars`, `--query`, `--json/--no-json`

---

### `neuralclaw fresh` — FreshApple snapshot
Generate a markdown snapshot of active context.

```bash
neuralclaw fresh --project mi-app
neuralclaw fresh --project mi-app --regenerate --ttl 7200
```

**Features:** TTL-based caching, auto-expiration, fresh flag.

---

### `neuralclaw delete` — Delete context item
Delete a context item by ID.

```bash
neuralclaw delete item_id_123 --force
```

---

## Projects

### `neuralclaw project create` — Create project
```bash
neuralclaw project create "mi-app" --description "Mi primer proyecto"
```

---

### `neuralclaw project list` — List projects
```bash
neuralclaw project list
neuralclaw project list --status archived
```

---

### `neuralclaw project status` — Project status
```bash
neuralclaw project status mi-app
```
Shows: total items, active, stale.

---

### `neuralclaw project archive` — Archive project
```bash
neuralclaw project archive mi-app
```

---

### `neuralclaw project delete` — Delete project
```bash
neuralclaw project delete mi-app --force
```
Deletes project and ALL its context items.

---

## Vault (Encrypted Secrets)

### `neuralclaw vault set` — Store secret
```bash
neuralclaw vault set OPENAI_API_KEY sk-...
```

---

### `neuralclaw vault get` — Retrieve secret
```bash
neuralclaw vault get OPENAI_API_KEY
neuralclaw vault get OPENAI_API_KEY --reveal  # Show value
```

---

### `neuralclaw vault list` — List secrets
```bash
neuralclaw vault list
```
Shows names only (values encrypted).

---

### `neuralclaw vault delete` — Delete secret
```bash
neuralclaw vault delete OPENAI_API_KEY --force
```

---

### `neuralclaw vault status` — Vault health
```bash
neuralclaw vault status
```

---

## Backup & Restore

### `neuralclaw backup` — Export all data
```bash
neuralclaw backup
neuralclaw backup --output backup.json
neuralclaw backup --project mi-app --output mi-app_backup.json.gz
```
Exports: projects, context items, vault metadata. **Vault values NOT exported** (security).

---

### `neuralclaw restore` — Restore from backup
```bash
neuralclaw restore backup.json
neuralclaw restore backup.json --replace
```

---

### `neuralclaw import-cmd` — Bulk import
```bash
neuralclaw import --from bulk.json --project mi-app
neuralclaw import --from items.jsonl
cat data.json | neuralclaw import --from -
```
Supports JSON (array) and JSONL formats.

---

## System

### `neuralclaw init` — Initialize
```bash
neuralclaw init
neuralclaw init --yes  # Non-interactive
```
Creates: config, database, vault, default project.

---

### `neuralclaw status` — Quick overview
```bash
neuralclaw status
```
Shows: version, schema, projects, context items, vault status, health.

---

### `neuralclaw doctor` — Health check
```bash
neuralclaw doctor
```
Checks: DB, vault, FTS5, indexes, stale items, schema.

---

### `neuralclaw version` — Version info
```bash
neuralclaw version
```

---

## Learning & Testing

### `neuralclaw tutorial` — Interactive walkthrough
```bash
neuralclaw tutorial
```
Step-by-step guide through all features.

---

### `neuralclaw examples` — Usage examples
```bash
neuralclaw examples
```
Real-world usage examples for all commands.

---

### `neuralclaw train-room analyze` — Analyze communication style
```bash
neuralclaw train-room analyze --samples /path/to/samples --model my-model
```
Analyzes conversation samples and generates a communication profile.

---

### `neuralclaw train-room list` — List profiles
```bash
neuralclaw train-room list
```

---

### `neuralclaw playroom test` — Test prompts across adapters
```bash
neuralclaw playroom test "write a hello world function" --adapter openclaw,claude,chatgpt
```

---

## Integrations

### `neuralclaw serve` — REST API server
```bash
neuralclaw serve --port 7890 --host 0.0.0.0
```
Starts: FastAPI server + web dashboard at http://localhost:7890/

---

### `neuralclaw tui` — Interactive TUI
```bash
neuralclaw tui
```
Rich-based terminal UI.

---

### `neuralclaw embeddings` — Compute embeddings
```bash
neuralclaw embeddings "hello world"
neuralclaw embeddings --model nomic-embed-text --pull
```

---

### `neuralclaw install-completion` — Shell completion
```bash
neuralclaw install-completion bash
neuralclaw install-completion zsh
neuralclaw install-completion fish
```

---

## Plugins

### `neuralclaw plugin list` — List plugins
```bash
neuralclaw plugin list
```

---

### `neuralclaw plugin enable` — Enable plugin
```bash
neuralclaw plugin enable audit
```

---

### `neuralclaw plugin disable` — Disable plugin
```bash
neuralclaw plugin disable audit
```

---

### `neuralclaw plugin info` — Plugin info
```bash
neuralclaw plugin info audit
```

---

## Configuration

### `neuralclaw config show` — Show config
```bash
neuralclaw config show
```

---

### `neuralclaw config set` — Set config value
```bash
neuralclaw config set search.method embeddings
neuralclaw config set ollama.base_url http://localhost:11434
neuralclaw config set ollama.enabled true
```

---

### `neuralclaw config ollama-status` — Ollama health
```bash
neuralclaw config ollama-status
```

---

## Context Item Types

| Type | Description |
|------|-------------|
| `note` | General note (default) |
| `decision` | Architectural decision |
| `error` | Error or bug |
| `variable` | Key-value variable |
| `preference` | User preference |
| `process` | Process or workflow |
| `industry` | Industry knowledge |

---

## Context Item States

| State | Description |
|-------|-------------|
| `active` | Currently valid (default) |
| `stale` | Past freshness TTL |
| `verified` | Confirmed correct |
| `deprecated` | No longer valid |
| `archived` | Archived manually |
| `conflicting` | Conflicts with other item |
| `unknown` | Unclassified |
| `old_school` | Legacy item |

---

## Context Adapters

Format context output for specific AI systems:

- **openclaw** — OpenClaw agent framework
- **chatgpt** — OpenAI ChatGPT
- **claude** — Anthropic Claude

---

## Architecture

- **Database:** SQLite at `~/.config/neuralclaw/neuralclaw.db`
- **Vault:** Fernet-encrypted at `~/.config/neuralclaw/vault.db`
- **Config:** YAML at `~/.config/neuralclaw/config.yaml`
- **Schema:** 8 tables + FTS5 virtual table + triggers
- **Python:** 3.11+
- **Dependencies:** typer, rich, pyyaml, cryptography, click

---

## Smart Features

### Type Inference
Automatically detects type from content patterns.

### Suggest Similar
"Did you mean?" hints when project/item not found.

### FreshApple
Markdown snapshots with TTL-based auto-expiration.

### Staleness Detection
Items automatically marked stale after configurable TTL.

### Conflict Detection
Identifies conflicting context items.

### Pagination
All search results support `--limit` and `--offset`.

---

*Last updated: 2026-04-28 | v0.4.1*
