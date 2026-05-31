"""Active-memory layer for Claude Code.

This module turns NeuralClaw's context store into an *active memory* for
Claude Code, applying the same memory principles NeuralClaw already uses for
its other adapters, but tuned for an agentic coding session:

  - **Relevance + recency + state ranking** — the most useful items float to
    the top, just like ``build_context_export`` ranks by ``relevance_score``.
  - **Token budgeting** — recall never blows the context window. Items are
    greedily packed into a token budget (default 2k) so memory injection stays
    cheap, mirroring the ``tokens_estimate`` accounting in ``core.bridge``.
  - **Stale flagging** — items past their ``stale_after`` TTL are demoted and
    annotated instead of silently trusted (FreshApple TTL principle).
  - **Progressive disclosure** — recall returns a compact one-line-per-item
    markdown block by default; full values are fetched on demand via the MCP
    ``memory_get`` tool rather than dumped up front.

Everything here is pure-Python and depends only on the existing core modules,
so it works without the optional ``mcp`` dependency installed.
"""

from __future__ import annotations

import time
from typing import Any

from neuralclaw.core.context import search_context
from neuralclaw.core.search import search_context_smart
from neuralclaw.core.projects import get_project

# Default token budget for a single recall injection. Kept small on purpose:
# active memory should be a sharp, relevant slice — not the whole store.
DEFAULT_TOKEN_BUDGET = 2000

# Rough chars-per-token ratio, matching core.bridge's estimate (len // 4).
CHARS_PER_TOKEN = 4

# How quickly an item's score decays with age. Half-life of ~30 days means a
# month-old item is worth half as much as a fresh one at equal relevance.
RECENCY_HALFLIFE_DAYS = 30.0

# State weights — verified knowledge is worth more than an unconfirmed note,
# stale/deprecated items are demoted, archived ones never surface.
STATE_WEIGHTS = {
    "verified": 1.30,
    "active": 1.00,
    "conflicting": 0.85,
    "stale": 0.50,
    "deprecated": 0.20,
    "archived": 0.0,
}

# Short glyphs so the rendered memory block stays token-cheap but scannable.
TYPE_GLYPHS = {
    "decision": "★",
    "error": "✗",
    "variable": "=",
    "preference": "♥",
    "process": "→",
    "industry": "§",
    "note": "·",
}


def estimate_tokens(text: str) -> int:
    """Estimate token count for a string (same heuristic as core.bridge)."""
    return max(1, len(text) // CHARS_PER_TOKEN)


def resolve_project_id(project: str | None) -> str | None:
    """Resolve a project name *or* id to its canonical id (None = global)."""
    if not project:
        return None
    found = get_project(project)
    return found["id"] if found else project


def score_item(item: dict[str, Any], now: int) -> float:
    """Compute a ranking score from relevance, recency, state and confidence.

    Higher is better. This is the heart of the token-optimization strategy:
    when the budget forces a cut, we keep the highest-scoring items.
    """
    relevance = float(item.get("relevance_score", 1.0) or 1.0)
    confidence = float(item.get("confidence", 1.0) or 1.0)
    state_weight = STATE_WEIGHTS.get(item.get("state", "active"), 1.0)

    # Recency decay based on last update.
    updated = int(item.get("updated_at") or item.get("created_at") or now)
    age_days = max(0.0, (now - updated) / 86400.0)
    recency = 0.5 ** (age_days / RECENCY_HALFLIFE_DAYS)

    # Extra penalty for an item that is already past its explicit TTL.
    stale_after = item.get("stale_after")
    stale_penalty = 0.6 if (stale_after and stale_after < now) else 1.0

    return relevance * confidence * state_weight * recency * stale_penalty


def is_stale(item: dict[str, Any], now: int) -> bool:
    """True if the item is past its TTL or already marked stale/conflicting."""
    if item.get("state") in ("stale", "conflicting"):
        return True
    stale_after = item.get("stale_after")
    return bool(stale_after and stale_after < now)


def rank_items(items: list[dict[str, Any]], now: int) -> list[dict[str, Any]]:
    """Drop archived items and sort the rest by descending score."""
    scored = [
        (score_item(it, now), it)
        for it in items
        if STATE_WEIGHTS.get(it.get("state", "active"), 1.0) > 0
    ]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [it for _score, it in scored]


def format_compact(item: dict[str, Any], now: int, value_chars: int = 90) -> str:
    """One token-cheap line per item: ``★ key: value  ⟨state·conf⟩``."""
    glyph = TYPE_GLYPHS.get(item.get("type", "note"), "·")
    key = item.get("key", "")
    value = (item.get("value") or "").replace("\n", " ").strip()
    if len(value) > value_chars:
        value = value[: value_chars - 1] + "…"

    flags = []
    if is_stale(item, now):
        flags.append("STALE")
    if item.get("state") == "conflicting":
        flags.append("CONFLICT")
    conf = float(item.get("confidence", 1.0) or 1.0)
    if conf < 1.0:
        flags.append(f"{conf:.0%}")
    suffix = f"  ⟨{'·'.join(flags)}⟩" if flags else ""

    return f"{glyph} `{key}`: {value}{suffix}"


def pack_within_budget(
    items: list[dict[str, Any]],
    token_budget: int,
    now: int,
) -> tuple[list[dict[str, Any]], int]:
    """Greedily select ranked items whose compact form fits the budget.

    Returns ``(selected_items, tokens_used)``. Items are assumed pre-ranked,
    so we keep the most valuable ones and stop once the budget is exhausted.
    """
    selected: list[dict[str, Any]] = []
    used = 0
    for item in items:
        line = format_compact(item, now)
        cost = estimate_tokens(line) + 1  # +1 for the newline / bullet overhead
        if used + cost > token_budget:
            continue  # skip this one but keep scanning for smaller items
        selected.append(item)
        used += cost
    return selected, used


def recall(
    query: str | None = None,
    project: str | None = None,
    token_budget: int = DEFAULT_TOKEN_BUDGET,
    method: str = "keyword",
    candidate_limit: int = 300,
) -> dict[str, Any]:
    """Retrieve a token-budgeted, ranked slice of memory for the active task.

    Args:
        query: Free-text task/query to focus recall. Empty => recent active memory.
        project: Project name or id (None => global memory).
        token_budget: Max tokens the rendered block may consume.
        method: Search method — ``keyword`` (default), ``fts`` or ``embeddings``.
        candidate_limit: How many raw rows to rank before packing.

    Returns a dict with the packed items, warnings and token accounting.
    """
    now = int(time.time())
    project_id = resolve_project_id(project)

    if query:
        candidates = search_context_smart(
            query=query,
            project_id=project_id,
            state="active",
            method=method,
            limit=candidate_limit,
        )
    else:
        # No query: fall back to the most recently updated active items.
        candidates = search_context(
            project_id=project_id, state="active", limit=candidate_limit
        )

    ranked = rank_items(candidates, now)
    selected, tokens_used = pack_within_budget(ranked, token_budget, now)

    warnings = []
    for item in selected:
        if is_stale(item, now):
            warnings.append(f"'{item.get('key')}' may be stale — verify before relying on it")
        if item.get("state") == "conflicting":
            warnings.append(f"'{item.get('key')}' has conflicting values — needs resolution")

    return {
        "query": query or "",
        "project": project or "global",
        "items": selected,
        "warnings": warnings,
        "considered": len(candidates),
        "returned": len(selected),
        "dropped": max(0, len(ranked) - len(selected)),
        "tokens_used": tokens_used,
        "token_budget": token_budget,
        "generated_at": now,
    }


def render_markdown(result: dict[str, Any]) -> str:
    """Render a recall result as a compact markdown memory block for Claude."""
    now = result.get("generated_at", int(time.time()))
    lines: list[str] = []
    scope = result.get("project", "global")
    header = f"## 🧠 NeuralClaw Memory — {scope}"
    if result.get("query"):
        header += f" · _{result['query']}_"
    lines.append(header)

    items = result.get("items", [])
    if not items:
        lines.append("_No relevant memory stored yet._")
        return "\n".join(lines)

    for item in items:
        lines.append(format_compact(item, now))

    if result.get("dropped"):
        lines.append(
            f"\n_+{result['dropped']} more items omitted to respect the "
            f"{result['token_budget']}-token budget — refine the query or call "
            f"`memory_recall` with a higher budget._"
        )

    warnings = result.get("warnings", [])
    if warnings:
        lines.append("\n**⚠️ Memory warnings:**")
        lines.extend(f"- {w}" for w in warnings)

    lines.append(
        f"\n_~{result.get('tokens_used', 0)} tokens · "
        f"{result.get('returned', 0)}/{result.get('considered', 0)} items_"
    )
    return "\n".join(lines)
