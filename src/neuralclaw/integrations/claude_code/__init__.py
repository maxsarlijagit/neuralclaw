"""Claude Code integration — NeuralClaw as active, token-optimized memory.

Public surface:
    memory   — ranking + token-budgeted recall logic
    scaffold — `cc install` config writers
    hook     — SessionStart memory-injection entrypoint
    mcp_server — MCP stdio server exposing memory tools to Claude Code
"""

from neuralclaw.integrations.claude_code import memory, scaffold  # noqa: F401

__all__ = ["memory", "scaffold"]
