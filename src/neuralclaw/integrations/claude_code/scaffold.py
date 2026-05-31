"""Scaffolding for wiring NeuralClaw into a Claude Code project.

``neuralclaw cc install`` writes (or merges) the config Claude Code needs:

  - ``.mcp.json``              registers the ``neuralclaw-memory`` MCP server
  - ``.claude/settings.json``  registers the SessionStart memory hook
  - ``CLAUDE.md``              appends a short note teaching the agent to use it

Existing files are merged, not clobbered: we only add our keys and leave the
rest of the user's configuration untouched.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

MCP_SERVER_KEY = "neuralclaw-memory"

CLAUDE_MD_MARKER = "<!-- neuralclaw:claude-code -->"

CLAUDE_MD_BLOCK = f"""{CLAUDE_MD_MARKER}
## 🧠 Persistent memory (NeuralClaw)

This project uses **NeuralClaw** as a local, cross-session active memory.

- At session start, relevant memory is auto-injected (SessionStart hook).
- During work, use the MCP tools from the `neuralclaw-memory` server:
  - `memory_recall(query, project, token_budget)` — load relevant decisions,
    errors and variables for the task, ranked and token-budgeted.
  - `memory_store(content, item_type, project)` — persist a decision, error,
    variable or fact so it survives future sessions.
  - `memory_get(item_id)` — expand the full value of one item.
  - `memory_snapshot(project)` — a FreshApple snapshot of active context.

**Principle:** prefer recalling stored memory over re-deriving context, and
store new decisions/errors as you make them. Respect items flagged `STALE` or
`CONFLICT`.
<!-- /neuralclaw:claude-code -->
"""


def _load_json(path: Path) -> dict[str, Any]:
    if path.exists():
        try:
            return json.loads(path.read_text() or "{}")
        except json.JSONDecodeError:
            return {}
    return {}


def _mcp_server_entry(project: str | None) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "command": "neuralclaw-cc-memory",
        "args": [],
    }
    if project:
        entry["env"] = {"NEURALCLAW_CC_PROJECT": project}
    return entry


def install_mcp_json(root: Path, project: str | None) -> bool:
    """Register the memory MCP server in ``.mcp.json``. Returns True if changed."""
    path = root / ".mcp.json"
    data = _load_json(path)
    servers = data.setdefault("mcpServers", {})
    new_entry = _mcp_server_entry(project)
    if servers.get(MCP_SERVER_KEY) == new_entry:
        return False
    servers[MCP_SERVER_KEY] = new_entry
    path.write_text(json.dumps(data, indent=2) + "\n")
    return True


def install_settings_hook(root: Path, project: str | None, token_budget: int | None) -> bool:
    """Register the SessionStart hook in ``.claude/settings.json``."""
    settings_dir = root / ".claude"
    settings_dir.mkdir(parents=True, exist_ok=True)
    path = settings_dir / "settings.json"
    data = _load_json(path)

    hooks = data.setdefault("hooks", {})
    session_start = hooks.setdefault("SessionStart", [])

    # Avoid duplicate registration.
    already = any(
        h.get("command") == "neuralclaw-cc-hook"
        for group in session_start
        if isinstance(group, dict)
        for h in group.get("hooks", [])
        if isinstance(h, dict)
    )
    if already:
        return False

    hook_cmd: dict[str, Any] = {"type": "command", "command": "neuralclaw-cc-hook"}
    session_start.append({"hooks": [hook_cmd]})

    # Stash optional env defaults so the hook picks them up.
    if project or token_budget:
        env = data.setdefault("env", {})
        if project:
            env["NEURALCLAW_CC_PROJECT"] = project
        if token_budget:
            env["NEURALCLAW_CC_TOKEN_BUDGET"] = str(token_budget)

    path.write_text(json.dumps(data, indent=2) + "\n")
    return True


def install_claude_md(root: Path) -> bool:
    """Append the usage note to ``CLAUDE.md`` if not already present."""
    path = root / "CLAUDE.md"
    existing = path.read_text() if path.exists() else ""
    if CLAUDE_MD_MARKER in existing:
        return False
    prefix = existing.rstrip() + "\n\n" if existing.strip() else ""
    path.write_text(prefix + CLAUDE_MD_BLOCK)
    return True


def install(
    root: Path,
    project: str | None = None,
    token_budget: int | None = None,
    with_hook: bool = True,
    with_mcp: bool = True,
    with_claude_md: bool = True,
) -> dict[str, bool]:
    """Run the requested scaffolding steps. Returns a map of step -> changed."""
    root = Path(root)
    results: dict[str, bool] = {}
    if with_mcp:
        results[".mcp.json"] = install_mcp_json(root, project)
    if with_hook:
        results[".claude/settings.json"] = install_settings_hook(root, project, token_budget)
    if with_claude_md:
        results["CLAUDE.md"] = install_claude_md(root)
    return results
