"""SessionStart hook: auto-inject NeuralClaw memory into Claude Code.

Claude Code runs ``SessionStart`` hooks when a session begins (startup, resume,
clear or compact). This script emits a compact, token-budgeted memory block as
``additionalContext`` so the agent starts every session already aware of the
project's decisions, errors and variables — the "active memory recall" step.

It is intentionally defensive: if NeuralClaw isn't initialised yet, it prints
nothing and exits 0 so it never blocks a session.

Configuration via environment variables (all optional):
    NEURALCLAW_CC_PROJECT        Project name/id to scope memory to.
    NEURALCLAW_CC_TOKEN_BUDGET   Token budget for the injected block (default 1500).
    NEURALCLAW_CC_QUERY          Optional focus query for recall.

Wire it up in ``.claude/settings.json`` (see ``neuralclaw cc install``)::

    {
      "hooks": {
        "SessionStart": [
          {"hooks": [{"type": "command", "command": "neuralclaw-cc-hook"}]}
        ]
      }
    }
"""

from __future__ import annotations

import json
import os
import sys


def _build_context() -> str:
    """Return the markdown memory block, or '' if nothing useful is available."""
    try:
        from neuralclaw.db.connection import db_exists

        if not db_exists():
            return ""

        from neuralclaw.integrations.claude_code import memory as mem

        project = os.environ.get("NEURALCLAW_CC_PROJECT") or None
        query = os.environ.get("NEURALCLAW_CC_QUERY") or None
        try:
            budget = int(os.environ.get("NEURALCLAW_CC_TOKEN_BUDGET", "1500"))
        except ValueError:
            budget = 1500

        result = mem.recall(query=query, project=project, token_budget=budget)
        if not result.get("items"):
            return ""
        block = mem.render_markdown(result)
        return (
            "The following is persistent memory recalled by NeuralClaw "
            "(local Context OS). Treat it as established project knowledge; "
            "prefer it over re-deriving context, and flag anything marked STALE "
            "or CONFLICT before relying on it.\n\n" + block
        )
    except Exception as exc:  # never break a session because of memory
        return f"<!-- NeuralClaw memory hook skipped: {exc} -->"


def main(argv: list[str] | None = None) -> int:
    # Claude Code passes hook input as JSON on stdin; we don't need it, but we
    # drain it so the pipe doesn't block.
    try:
        if not sys.stdin.isatty():
            sys.stdin.read()
    except Exception:
        pass

    context = _build_context()
    if not context.strip():
        return 0

    payload = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": context,
        }
    }
    json.dump(payload, sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
