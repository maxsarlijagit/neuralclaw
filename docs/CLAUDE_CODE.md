# NeuralClaw as Active Memory for Claude Code

NeuralClaw can act as **persistent, local, cross-session memory for Claude
Code**, applying the same memory principles and token optimization it already
uses for its other adapters — but tuned for an agentic coding session.

This integration gives Claude Code three things:

1. **Auto-recall at session start** — a `SessionStart` hook injects a compact,
   token-budgeted slice of your most relevant decisions, errors and variables.
2. **Active read/write during the session** — an MCP server exposes
   `memory_recall`, `memory_store`, `memory_get` and `memory_snapshot` so the
   agent can pull context on demand and persist new facts as it works.
3. **A token-optimized adapter** (`claude-code`) for `neuralclaw context`.

---

## Memory principles & token optimization

The integration mirrors how Claude Code itself manages context — keep the
working set small, relevant, and progressively disclosed:

| Principle | How NeuralClaw applies it |
|-----------|---------------------------|
| **Relevance ranking** | Items scored by `relevance_score × confidence × state weight × recency`. The best float to the top. |
| **Token budgeting** | Recall greedily packs items into a token budget (default 2000) and never overflows the window. Dropped items are reported, not silently lost. |
| **Recency decay** | Score halves roughly every 30 days, so fresh knowledge wins ties. |
| **State weighting** | `verified` > `active` > `conflicting` > `stale` > `deprecated`; `archived` never surfaces. |
| **Stale flagging** | Items past their TTL are demoted and annotated `STALE`; conflicts are flagged `CONFLICT`. |
| **Progressive disclosure** | Recall returns one compact line per item; full values are fetched on demand via `memory_get`. |

Token accounting uses the same `chars // 4` heuristic as the core context
bridge, so estimates stay consistent across the project.

---

## Install

```bash
# 1. Install NeuralClaw with the Claude Code extra (pulls in the `mcp` package)
pip install "neuralclaw-os[claude-code]"

# 2. Initialise NeuralClaw (once per machine)
neuralclaw init

# 3. Wire it into your project (writes .mcp.json + .claude/settings.json + CLAUDE.md)
cd your-project
neuralclaw cc install --project your-project
```

Then restart Claude Code so it picks up the new MCP server and hook.

`cc install` is idempotent and merges into existing config — it never clobbers
your files. Flags: `--no-hook`, `--no-mcp`, `--no-claude-md`, `--budget`,
`--path`.

---

## What gets written

**`.mcp.json`** — registers the memory server:

```json
{
  "mcpServers": {
    "neuralclaw-memory": {
      "command": "neuralclaw-cc-memory",
      "env": { "NEURALCLAW_CC_PROJECT": "your-project" }
    }
  }
}
```

**`.claude/settings.json`** — registers the auto-recall hook:

```json
{
  "hooks": {
    "SessionStart": [
      { "hooks": [{ "type": "command", "command": "neuralclaw-cc-hook" }] }
    ]
  },
  "env": { "NEURALCLAW_CC_TOKEN_BUDGET": "1500" }
}
```

**`CLAUDE.md`** — a short note teaching the agent to recall before re-deriving
and to store decisions as it makes them.

---

## MCP tools available to Claude Code

| Tool | Purpose |
|------|---------|
| `memory_recall(query, project, token_budget, method)` | Ranked, token-budgeted retrieval for the current task. |
| `memory_store(content, item_type, project, tags, confidence)` | Persist a decision / error / variable / fact (type auto-detected). |
| `memory_get(item_id)` | Expand the full value of a single item. |
| `memory_snapshot(project)` | FreshApple markdown snapshot of active context. |

---

## CLI equivalents

Everything the agent can do, you can do from the terminal:

```bash
# Recall relevant memory for a task (token-budgeted markdown)
neuralclaw cc recall "implement auth refresh" --project your-project --budget 1500

# Store a fact (type auto-detected: decision/error/variable/...)
neuralclaw cc remember "decision: refresh tokens 60s before expiry" -p your-project

# A full snapshot of active context
neuralclaw cc snapshot --project your-project
```

---

## Configuration (environment variables)

| Variable | Effect | Default |
|----------|--------|---------|
| `NEURALCLAW_CC_PROJECT` | Scope auto-recall / MCP server to a project | global |
| `NEURALCLAW_CC_TOKEN_BUDGET` | Token budget for the SessionStart block | `1500` |
| `NEURALCLAW_CC_QUERY` | Optional focus query for auto-recall | none |

The hook is defensive: if NeuralClaw isn't initialised, or there's no relevant
memory, it prints nothing and exits cleanly — it never blocks a session.
