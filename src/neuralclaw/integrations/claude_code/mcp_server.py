"""MCP server exposing NeuralClaw as active memory for Claude Code.

Claude Code talks to NeuralClaw over the Model Context Protocol (stdio). This
server gives the agent four memory operations during a live session:

  - ``memory_recall``   — token-budgeted, ranked retrieval for the current task
  - ``memory_store``    — persist a decision / error / variable / note
  - ``memory_get``      — fetch the full value of one item (progressive disclosure)
  - ``memory_snapshot`` — a FreshApple markdown snapshot of active context

The ``mcp`` package is an *optional* dependency. Install it with::

    pip install "neuralclaw-os[claude-code]"

Run the server directly::

    neuralclaw-cc-memory
    # or
    python -m neuralclaw.integrations.claude_code.mcp_server
"""

from __future__ import annotations

import sys

from neuralclaw.integrations.claude_code import memory as mem


def _require_mcp():
    """Import FastMCP, with a friendly error if the extra isn't installed."""
    try:
        from mcp.server.fastmcp import FastMCP  # type: ignore
    except ModuleNotFoundError as exc:  # pragma: no cover - depends on env
        raise SystemExit(
            "The 'mcp' package is required for the Claude Code memory server.\n"
            "Install it with:  pip install \"neuralclaw-os[claude-code]\"\n"
            f"(import error: {exc})"
        )
    return FastMCP


def build_server():
    """Construct and return the configured FastMCP server instance."""
    FastMCP = _require_mcp()
    from neuralclaw.core.context import add_context_item, get_context_item
    from neuralclaw.core.fresh import generate_fresh_apple
    from neuralclaw.cli.main import _infer_type_from_content  # smart type detection

    server = FastMCP(
        "neuralclaw-memory",
        instructions=(
            "NeuralClaw is your persistent, local, cross-session memory. "
            "Call memory_recall at the start of a task to load relevant decisions, "
            "errors and variables within a token budget. Call memory_store whenever "
            "you make a decision, hit an error, or learn a project fact, so it "
            "survives future sessions. Prefer recall over re-deriving known context."
        ),
    )

    @server.tool()
    def memory_recall(
        query: str = "",
        project: str = "",
        token_budget: int = mem.DEFAULT_TOKEN_BUDGET,
        method: str = "keyword",
    ) -> str:
        """Recall token-budgeted, relevance-ranked memory for the current task.

        Args:
            query: What you're working on (free text). Empty = recent active memory.
            project: Project name or id to scope to. Empty = global memory.
            token_budget: Max tokens the returned block may use (default 2000).
            method: 'keyword' (default), 'fts', or 'embeddings' (needs Ollama).
        """
        result = mem.recall(
            query=query or None,
            project=project or None,
            token_budget=token_budget,
            method=method,
        )
        return mem.render_markdown(result)

    @server.tool()
    def memory_store(
        content: str,
        key: str = "",
        item_type: str = "",
        project: str = "",
        tags: str = "",
        confidence: float = 1.0,
    ) -> str:
        """Persist a fact into long-term memory.

        Args:
            content: The thing to remember (the value).
            key: Short stable identifier. Defaults to a slug of the content.
            item_type: note | decision | error | variable | preference | process.
                       Empty = auto-detected from the content.
            project: Project name or id to scope to. Empty = global.
            tags: Comma-separated tags.
            confidence: 0..1 confidence in this fact.
        """
        project_id = mem.resolve_project_id(project or None)
        inferred_type, inferred_tags, inferred_key = _infer_type_from_content(content)
        resolved_type = item_type or inferred_type
        resolved_key = key or (inferred_key if inferred_key != "note" else _slug(content))
        tag_list = [t.strip() for t in tags.split(",") if t.strip()] or inferred_tags or None
        item_id = add_context_item(
            project_id=project_id,
            key=resolved_key,
            value=content,
            item_type=resolved_type,
            tags=tag_list,
            confidence=confidence,
        )
        return (
            f"Stored [{resolved_type}] `{resolved_key}` "
            f"(project={project or 'global'}, id={item_id})"
        )

    @server.tool()
    def memory_get(item_id: str) -> str:
        """Fetch the full value of a single memory item by its id."""
        item = get_context_item(item_id)
        if not item:
            return f"No memory item with id '{item_id}'."
        return (
            f"[{item.get('type')}] {item.get('key')} (state={item.get('state')})\n"
            f"{item.get('value')}"
        )

    @server.tool()
    def memory_snapshot(project: str = "") -> str:
        """Return a FreshApple markdown snapshot of active context.

        Args:
            project: Project name or id. Empty = global snapshot across projects.
        """
        project_id = mem.resolve_project_id(project or None)
        return generate_fresh_apple(project_id=project_id, project_name=project or None)

    return server


def _slug(text: str, max_len: int = 40) -> str:
    """Make a short, stable-ish key from free text."""
    cleaned = "".join(c if c.isalnum() or c in " -_" else " " for c in text.lower())
    words = cleaned.split()
    slug = "-".join(words)[:max_len].strip("-")
    return slug or "memory"


def main(argv: list[str] | None = None) -> int:
    """Entry point for the ``neuralclaw-cc-memory`` console script."""
    server = build_server()
    server.run()  # stdio transport by default
    return 0


if __name__ == "__main__":
    sys.exit(main())
