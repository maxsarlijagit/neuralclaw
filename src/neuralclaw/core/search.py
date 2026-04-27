"""Advanced search: FTS5 full-text and semantic embeddings search."""

import json
import math
import time
from typing import Any, Optional

from neuralclaw.db.connection import get_connection
from neuralclaw.core.embeddings import (
    OllamaEmbeddings,
    cosine_similarity,
    get_embeddings_client,
)


def _simple_query(query: str) -> bool:
    """Check if query is a simple keyword query (no FTS operators)."""
    # FTS5 special operators: *, ", -, (, ), AND, OR, NOT
    fts_keywords = {"AND", "OR", "NOT", "ANDNOT", "ORNOT", "NOTAND", "NOTOR"}
    parts = query.upper().split()
    return not any(p in fts_keywords for p in parts) and '"' not in query


def _build_fts_query(query: str) -> str:
    """Convert user query to FTS5 MATCH query."""
    # Add prefix matching for partial words
    tokens = query.strip().split()
    if len(tokens) == 1:
        return f"{tokens[0]}*"
    # Multi-word: use phrase matching or AND
    return " ".join(tokens)


def search_context_fts(
    query: str,
    project_id: str | None = None,
    state: str | None = None,
    item_type: str | None = None,
    tags: list[str] | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Search using FTS5 full-text search."""
    if not query:
        return []

    fts_query = _build_fts_query(query)

    sql_parts = [
        "SELECT c.*, rank FROM context_items c",
        "JOIN context_fts ON c.rowid = context_fts.rowid",
        "WHERE context_fts MATCH ?",
    ]
    params = [fts_query]

    if project_id is not None:
        sql_parts.append("AND c.project_id = ?")
        params.append(project_id)

    if state is not None:
        sql_parts.append("AND c.state = ?")
        params.append(state)

    if item_type is not None:
        sql_parts.append("AND c.type = ?")
        params.append(item_type)

    sql_parts.append("ORDER BY rank LIMIT ?")
    params.append(limit)

    with get_connection() as conn:
        rows = conn.execute(" ".join(sql_parts), params).fetchall()

    results = []
    for row in rows:
        r = dict(row)
        # Remove the 'rank' column that FTS adds
        r.pop("rank", None)
        r["tags"] = json.loads(r["tags"]) if r["tags"] else []
        r["sources"] = json.loads(r["sources"]) if r["sources"] else []
        results.append(r)

    return results


def search_context_embeddings(
    query: str,
    project_id: str | None = None,
    state: str | None = None,
    item_type: str | None = None,
    tags: list[str] | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Search using Ollama embeddings (semantic search)."""
    client = get_embeddings_client()

    if client is None:
        return []

    # Compute query embedding
    query_emb = client.embed(query)
    if not query_emb:
        return []

    # Get candidate items (broader search for embedding comparison)
    # Fetch up to 500 items, then rerank by similarity
    candidates = _get_all_candidates(
        project_id=project_id,
        state=state,
        item_type=item_type,
        tags=tags,
        limit=500,
    )

    # Compute embeddings for each candidate's key+value text
    scored = []
    for item in candidates:
        text = f"{item['key']} {item['value']}"

        # Simple cache: we don't implement a full embedding cache here
        # to keep it lightweight. In production you'd want a proper cache.
        emb = client.embed(text)
        if emb:
            sim = cosine_similarity(query_emb, emb)
            item_copy = dict(item)
            item_copy["_similarity"] = round(sim, 4)
            scored.append(item_copy)

    # Sort by similarity descending
    scored.sort(key=lambda x: x["_similarity"], reverse=True)

    # Remove internal field and return top results
    for item in scored[:limit]:
        item.pop("_similarity", None)

    return scored[:limit]


def search_context_keyword(
    query: str,
    project_id: str | None = None,
    state: str | None = None,
    item_type: str | None = None,
    tags: list[str] | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Search using LIKE (keyword fallback)."""
    sql_parts = ["SELECT * FROM context_items WHERE 1=1"]
    params = []

    if project_id is not None:
        sql_parts.append("AND project_id = ?")
        params.append(project_id)

    if state is not None:
        sql_parts.append("AND state = ?")
        params.append(state)

    if item_type is not None:
        sql_parts.append("AND type = ?")
        params.append(item_type)

    if query:
        sql_parts.append("AND (key LIKE ? OR value LIKE ?)")
        params.extend([f"%{query}%", f"%{query}%"])

    sql_parts.append("ORDER BY updated_at DESC LIMIT ?")
    params.append(limit)

    with get_connection() as conn:
        rows = conn.execute(" ".join(sql_parts), params).fetchall()

    results = []
    for row in rows:
        r = dict(row)
        r["tags"] = json.loads(r["tags"]) if r["tags"] else []
        r["sources"] = json.loads(r["sources"]) if r["sources"] else []
        results.append(r)

    return results


def search_context_smart(
    query: str,
    project_id: str | None = None,
    state: str | None = None,
    item_type: str | None = None,
    tags: list[str] | None = None,
    method: str = "keyword",
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Smart search that picks the best method based on query complexity and config.

    Args:
        query: Search query
        method: 'keyword', 'fts', or 'embeddings'
        project_id, state, item_type, tags: Filters
        limit: Max results

    Returns:
        List of matching context items with relevance info
    """
    if method == "embeddings":
        return search_context_embeddings(
            query=query,
            project_id=project_id,
            state=state,
            item_type=item_type,
            tags=tags,
            limit=limit,
        )

    if method == "fts":
        return search_context_fts(
            query=query,
            project_id=project_id,
            state=state,
            item_type=item_type,
            tags=tags,
            limit=limit,
        )

    # keyword / auto
    if query and not _simple_query(query):
        # Complex query → FTS
        return search_context_fts(
            query=query,
            project_id=project_id,
            state=state,
            item_type=item_type,
            tags=tags,
            limit=limit,
        )

    return search_context_keyword(
        query=query,
        project_id=project_id,
        state=state,
        item_type=item_type,
        tags=tags,
        limit=limit,
    )


def _get_all_candidates(
    project_id: str | None = None,
    state: str | None = None,
    item_type: str | None = None,
    tags: list[str] | None = None,
    limit: int = 500,
) -> list[dict[str, Any]]:
    """Fetch all candidate items for embedding reranking."""
    sql_parts = ["SELECT * FROM context_items WHERE 1=1"]
    params = []

    if project_id is not None:
        sql_parts.append("AND project_id = ?")
        params.append(project_id)
    if state is not None:
        sql_parts.append("AND state = ?")
        params.append(state)
    if item_type is not None:
        sql_parts.append("AND type = ?")
        params.append(item_type)

    sql_parts.append("ORDER BY updated_at DESC LIMIT ?")
    params.append(limit)

    with get_connection() as conn:
        rows = conn.execute(" ".join(sql_parts), params).fetchall()

    results = []
    for row in rows:
        r = dict(row)
        r["tags"] = json.loads(r["tags"]) if r["tags"] else []
        r["sources"] = json.loads(r["sources"]) if r["sources"] else []
        results.append(r)

    return results


def suggest_context(
    query: str,
    project_id: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Find related context items using semantic similarity.

    Args:
        query: Partial description of what you're looking for
        project_id: Optional project filter
        limit: Max suggestions

    Returns:
        List of context items sorted by semantic relevance
    """
    client = get_embeddings_client()

    if client is None:
        return []

    query_emb = client.embed(query)
    if not query_emb:
        return []

    candidates = _get_all_candidates(project_id=project_id, limit=500)

    scored = []
    for item in candidates:
        text = f"{item['key']} {item['value']}"
        emb = client.embed(text)
        if emb:
            sim = cosine_similarity(query_emb, emb)
            if sim > 0.3:  # Only suggest relevant items
                item_copy = dict(item)
                item_copy["_relevance"] = round(sim, 4)
                scored.append(item_copy)

    scored.sort(key=lambda x: x["_relevance"], reverse=True)

    for item in scored[:limit]:
        item.pop("_relevance", None)

    return scored[:limit]