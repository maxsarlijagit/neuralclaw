<div align="center">

<br/>
███╗ ██╗███████╗██╗ ██╗██████╗ █████╗ ██╗ ██████╗██╗ █████╗ ██╗ ██╗
████╗ ██║██╔════╝██║ ██║██╔══██╗██╔══██╗██║ ██╔════╝██║ ██╔══██╗██║ ██║
██╔██╗ ██║█████╗ ██║ ██║██████╔╝███████║██║ ██║ ██║ ███████║██║ █╗ ██║
██║╚██╗██║██╔══╝ ██║ ██║██╔══██╗██╔══██║██║ ██║ ██║ ██╔══██║██║███╗██║
██║ ╚████║███████╗╚██████╔╝██║ ██║██║ ██║███████╗╚██████╗███████╗██║ ██║
╚███╔███╔╝
╚═══╝ ╚═══╝╚══════╝ ╚═════╝ ╚═╝ ╚═╝╚══════╝ ╚═════╝╚══════╝╚═╝ ╚═╝

**Local Context OS for AI Agents**

<br/>

[![PyPI version](https://img.shields.io/pypi/v/neuralclaw-os?color=00ff88&labelColor=0a0a0a&style=flat-square)](https://pypi.org/project/neuralclaw-os/)
[![Python](https://img.shields.io/pypi/pyversions/neuralclaw-os?color=00ff88&labelColor=0a0a0a&style=flat-square)](https://pypi.org/project/neuralclaw-os/)
[![License](https://img.shields.io/github/license/maxsarlijagit/neuralclaw?color=00ff88&labelColor=0a0a0a&style=flat-square)](LICENSE)
[![GitHub Stars](https://img.shields.io/github/stars/maxsarlijagit/neuralclaw?color=00ff88&labelColor=0a0a0a&style=flat-square)](https://github.com/maxsarlijagit/neuralclaw)

<br/>
pip install neuralclaw-os

</div>

-----

## The problem

You're mid-session with Claude. You switch to ChatGPT. You open a new agent.

Everything you just built — the context — is gone.

You copy-paste. You re-explain. You lose the thread.

This is the real bottleneck in multi-agent workflows. Not the model. Not the prompt. The context.

-----

## What NeuralClaw does

NeuralClaw is a **Local Context OS for AI Agents** — a CLI that acts as persistent memory across all your AI tools.

You store decisions, errors, variables, and project state once. When you switch agents or start a new session, NeuralClaw formats and delivers the right context automatically — for whichever AI you're using.

- **Local-first.** No cloud. Everything lives on your machine.
- **Encrypted vault** for secrets and sensitive config.
- **Multi-adapter output** — exports formatted for OpenClaw, Claude, or ChatGPT.
- **Semantic search** via Ollama embeddings.
- **REST API + TUI** for integrations.

-----

## Quickstart

```bash
# Install
pip install neuralclaw-os

# Initialize
neuralclaw init

# Create a project
neuralclaw project create my-project

# Add context
neuralclaw add "Using Pydantic v2 for all models — breaking change from v1" --project my-project
neuralclaw add "API rate limit is 100 req/min" --type variable --project my-project
neuralclaw add "Auth tokens expire after 15min — session refresh needed" --type decision --project my-project

# Get context formatted for your AI
neuralclaw context --project my-project --adapter claude

# Run the interactive tutorial
neuralclaw tutorial
```

-----

## Feature Reference

### Context Management

|Command |Description |
|---------|------------------------------------------------|
|`add` |Add context item (smart type inference) |
|`search` |Search with filters + interactive mode |
|`suggest`|Semantic search via Ollama embeddings |
|`context`|Export formatted for OpenClaw / Claude / ChatGPT|
|`fresh` |FreshApple markdown snapshots (TTL cache) |
|`delete` |Delete context item by ID |

Context types: note · decision · error · variable · preference · process · industry

States: active · stale · verified · deprecated · archived · conflicting

Adapters: openclaw · claude · chatgpt

-----

### Projects

|Command |Description |
|---------|--------------------------|
|`project create` |Create project |
|`project list` |List all projects |
|`project status` |Stats + item counts |
|`project archive`|Archive project |
|`project delete` |Delete project + all items|

-----

### Vault — Encrypted Secrets

|Command |Description |
|---------|--------------------------|
|`vault set` |Store secret |
|`vault get` |Retrieve secret |
|`vault list` |List secrets (names only)|
|`vault delete`|Delete secret |
|`vault status`|Health check |

-----

### Backup & Import

|Command |Description |
|---------|----------------------|
|`backup` |Export all (JSON/GZ) |
|`restore`|Restore from backup |
|`import` |Bulk import JSON/JSONL |

-----

### System

|Command |Description |
|---------|------------------------|
|`init` |Initialize NeuralClaw |
|`status` |Quick dashboard overview|
|`doctor` |Health checks |
|`version`|Version info |

-----

### Learning & Testing

|Command |Description |
|---------|---------------------------------------|
|`tutorial` |Interactive walkthrough |
|`examples` |Real-world usage examples |
|`train-room analyze`|Analyze samples → communication profile|
|`train-room list` |List saved profiles |
|`playroom test` |Test prompt across adapters |

-----

### Integrations

|Command |Description |
|---------|--------------------------------|
|`serve` |FastAPI REST API + web dashboard|
|`tui` |Interactive terminal UI |
|`embeddings` |Compute Ollama embeddings |
|`install-completion`|Shell completion (bash/zsh/fish)|

-----

### Claude Code — Active Memory

Use NeuralClaw as **persistent, token-optimized memory for Claude Code**: auto-recall at session start, plus MCP tools to read/write memory mid-session.

|Command |Description |
|---------|----------------------------------------------|
|`cc install` |Wire into a project (.mcp.json + hook + CLAUDE.md)|
|`cc recall` |Token-budgeted, ranked memory for a task |
|`cc remember`|Persist a decision/error/variable |
|`cc snapshot`|FreshApple snapshot of active context |

```bash
pip install "neuralclaw-os[claude-code]"
neuralclaw init
neuralclaw cc install --project my-project   # then restart Claude Code
```

The same principles NeuralClaw uses elsewhere — relevance + recency + state ranking, token budgeting, stale flagging, progressive disclosure — are tuned here for an agentic coding session.

📖 **Tutorial completo (ES):** [GUIA_CLAUDE.md](GUIA_CLAUDE.md) — instalación, uso en Claude Code, Claude Desktop y claude.ai, paso a paso.
📖 **Reference (EN):** [docs/CLAUDE_CODE.md](docs/CLAUDE_CODE.md).

-----

### Plugins

|Command |Description |
|---------|--------------|
|`plugin list` |List plugins |
|`plugin enable/disable`|Toggle plugin |
|`plugin info` |Plugin details|

-----

### Configuration

|Command |Description |
|---------|-------------|
|`config show` |Show config |
|`config set` |Set value |
|`config ollama-status`|Ollama health|

-----

## Why local-first

Most AI tooling assumes you live inside one ecosystem. NeuralClaw assumes you don't.

Your context is yours. It never leaves your machine. No account. No API key for NeuralClaw itself. No sync service watching your decisions and errors.

The vault uses encryption at rest. The backup format is open JSON — you can read it, port it, version it.

-----

## What's new in v0.4.1

- **Smart type inference** — add auto-detects variable / decision / error from natural language
- **Interactive search mode** — navigate results without leaving the CLI
- **`neuralclaw tutorial`** — step-by-step interactive walkthrough
- **`neuralclaw examples`** — real-world usage examples
- **Shell completion installer** — bash, zsh, and fish support via `install-completion`
- **`neuralclaw status`** — quick system dashboard
- **Verbose and quiet output modes** (`--verbose` / `--quiet`)

-----

## Roadmap

- [ ] VS Code extension
- [ ] More adapters (Gemini, Mistral, local Ollama agents)
- [ ] Context diff — track how decisions evolve over time
- [ ] Team mode (optional, self-hosted)

-----

## Contributing

PRs welcome. Open an issue first for large changes.

```bash
git clone https://github.com/maxsarlijagit/neuralclaw
cd neuralclaw
pip install -e ".[dev]"
```

-----

## License

MIT — see <LICENSE>

-----

<div align="center">

Built by [Max Sarlija](https://github.com/maxsarlijagit) · [PyPI](https://pypi.org/project/neuralclaw-os/) · [Issues](https://github.com/maxsarlijagit/neuralclaw/issues)

<br/>

*Stop copying context. Start building.*

</div>
