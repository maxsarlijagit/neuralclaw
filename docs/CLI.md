# NeuralClaw CLI Reference

## Global Options

```
--help     Show help and exit
--version  Show version
```

## Commands

### `neuralclaw init`

Initialize NeuralClaw: creates config, database, and vault.

```bash
neuralclaw init
```

### `neuralclaw add`

Add a context item.

```bash
neuralclaw add "key=value" [OPTIONS]
```

**Options:**
- `--project, -p <name>` — Project name or ID
- `--type, -t <type>` — Item type: `note` (default), `decision`, `error`, `variable`, `preference`
- `--tags <tags>` — Comma-separated tags
- `--stale-after <unix_ts>` — Unix timestamp after which item is stale
- `--confidence <0.0-1.0>` — Confidence level (default: 1.0)
- `--state, -s <state>` — State: `active` (default), `stale`, `verified`, `deprecated`, `archived`, `conflicting`

**Examples:**

```bash
neuralclaw add "api_url=https://api.example.com" --type variable --tags api,production
neuralclaw add "db_host=localhost" --project my-project
neuralclaw add "use_https=false" --type decision --tags security --confidence 0.8
```

---

### `neuralclaw search`

Search context items.

```bash
neuralclaw search [QUERY] [OPTIONS]
```

**Options:**
- `--project, -p <name>` — Filter by project
- `--state, -s <state>` — Filter by state
- `--type, -t <type>` — Filter by type
- `--tags <tags>` — Filter by comma-separated tags
- `--limit, -l <n>` — Max results (default: 50)
- `--json` — Output as JSON

**Examples:**

```bash
neuralclaw search api
neuralclaw search --project my-project --type variable
neuralclaw search "database" --tags production --json
```

---

### `neuralclaw context`

Export context as JSON for an AI agent.

```bash
neuralclaw context [OPTIONS]
```

**Options:**
- `--task, -t <desc>` — Task description
- `--project, -p <name>` — Project name or ID
- `--adapter, -a <name>` — Adapter: `openclaw` (default), `chatgpt`, `claude`
- `--include-vars` — Reveal vault variable values
- `--query, -q <query>` — Search query to filter context
- `--json` — Output as JSON (default: true)

**Examples:**

```bash
neuralclaw context --task "Deploy to production" --adapter openclaw
neuralclaw context -t "Debug issue" -p my-project --include-vars
```

---

### `neuralclaw import`

Bulk import context items from a file.

```bash
neuralclaw import --from <file> [OPTIONS]
```

**Options:**
- `--from, -f <file>` — Input file (JSON or JSONL)
- `--project, -p <name>` — Default project for items

**Input formats:**

**JSON:**
```json
[
  {"key": "api_url", "value": "https://api.example.com", "type": "variable"},
  {"key": "db_host", "value": "localhost", "type": "variable"}
]
```

**JSONL:**
```json
{"key": "api_url", "value": "https://api.example.com", "type": "variable"}
{"key": "db_host", "value": "localhost", "type": "variable"}
```

---

### `neuralclaw project`

Manage projects.

```bash
neuralclaw project create <name> [OPTIONS]
neuralclaw project list [OPTIONS]
neuralclaw project archive <name>
neuralclaw project delete <name> [OPTIONS]
neuralclaw project status <name>
```

**Sub-commands:**

- `create` — Create a new project
  - `--description, -d <desc>` — Project description

- `list` — List all projects
  - `--status, -s <status>` — Filter: `active`, `archived`

- `archive` — Archive a project

- `delete` — Delete a project and all its context items
  - `--force, -f` — Skip confirmation

- `status` — Show project status

**Examples:**

```bash
neuralclaw project create my-app --description "My application"
neuralclaw project list
neuralclaw project status my-app
neuralclaw project archive my-app
neuralclaw project delete my-app --force
```

---

### `neuralclaw vault`

Manage encrypted secrets.

```bash
neuralclaw vault set <name> [value]
neuralclaw vault get <name> [OPTIONS]
neuralclaw vault list
neuralclaw vault delete <name> [OPTIONS]
neuralclaw vault status
```

**Sub-commands:**

- `set` — Store a secret (prompts for value if not provided)
- `get` — Retrieve a secret
  - `--reveal` — Show the actual value
- `list` — List all secrets (names only)
- `delete` — Delete a secret
  - `--force, -f` — Skip confirmation
- `status` — Show vault status

**Examples:**

```bash
neuralclaw vault set OPENAI_API_KEY sk-...
neuralclaw vault set MY_SECRET my_value
neuralclaw vault get OPENAI_API_KEY --reveal
neuralclaw vault list
neuralclaw vault delete MY_SECRET --force
```

---

### `neuralclaw doctor`

Run health checks on the NeuralClaw installation.

```bash
neuralclaw doctor
```

Checks:
- Config directory exists
- Database initialized
- Schema version current
- Vault initialized
- FTS5 available
- Index integrity
- Recent errors in logs

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error |
