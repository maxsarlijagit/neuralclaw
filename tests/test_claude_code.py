"""Tests for the Claude Code active-memory integration."""

import json
import time

import pytest

from neuralclaw.core.context import add_context_item
from neuralclaw.core.projects import create_project
from neuralclaw.integrations.claude_code import memory as mem
from neuralclaw.integrations.claude_code import hook, scaffold


@pytest.fixture
def demo_project(fresh_db):
    """A project pre-seeded with a few memory items of different types."""
    pid = create_project("demo", "demo project")
    add_context_item(pid, "datastore", "decision: use Postgres for the datastore",
                     "decision", tags=["architecture"])
    add_context_item(pid, "API_RATE_LIMIT", "API_RATE_LIMIT=100 req/min", "variable")
    add_context_item(pid, "error-auth", "BUG: auth token expires after 15min", "error")
    add_context_item(pid, "minor", "minor styling note", "note", confidence=0.4)
    return pid


def test_estimate_tokens_matches_bridge_heuristic():
    assert mem.estimate_tokens("a" * 40) == 10
    assert mem.estimate_tokens("") == 1  # floor at 1


def test_state_weight_archived_is_excluded(fresh_db):
    pid = create_project("p", "")
    add_context_item(pid, "keep", "active fact", "note")
    add_context_item(pid, "gone", "archived fact", "note", state="archived")
    result = mem.recall(project="p", token_budget=1000)
    keys = {it["key"] for it in result["items"]}
    assert "keep" in keys
    assert "gone" not in keys


def test_recall_respects_token_budget(demo_project):
    """A tight budget must drop items and report the omission."""
    result = mem.recall(project="demo", token_budget=30)
    assert result["tokens_used"] <= 30
    assert result["dropped"] > 0
    assert result["returned"] + result["dropped"] <= result["considered"]


def test_recall_ranks_query_match_first(demo_project):
    result = mem.recall(query="auth token", project="demo", token_budget=2000)
    assert result["returned"] >= 1
    # The auth error should surface for an auth-related query.
    assert any("auth" in it["key"] for it in result["items"])


def test_recall_global_scope(demo_project):
    # No project filter still returns the demo items (global view).
    result = mem.recall(token_budget=2000)
    assert result["returned"] >= 1


def test_stale_item_is_flagged(fresh_db):
    pid = create_project("p", "")
    past = int(time.time()) - 10
    add_context_item(pid, "old", "expired fact", "note", stale_after=past)
    result = mem.recall(project="p", token_budget=1000)
    assert any("STALE" in mem.format_compact(it, int(time.time())) for it in result["items"])
    assert result["warnings"]


def test_render_markdown_compact(demo_project):
    result = mem.recall(project="demo", token_budget=2000)
    md = mem.render_markdown(result)
    assert md.startswith("## 🧠 NeuralClaw Memory")
    assert "tokens" in md


def test_render_markdown_empty(fresh_db):
    create_project("empty", "")
    result = mem.recall(project="empty", token_budget=1000)
    md = mem.render_markdown(result)
    assert "No relevant memory" in md


def test_hook_emits_session_start_json(demo_project, monkeypatch, capsys):
    monkeypatch.setenv("NEURALCLAW_CC_PROJECT", "demo")
    monkeypatch.setenv("NEURALCLAW_CC_TOKEN_BUDGET", "300")
    rc = hook.main([])
    assert rc == 0
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert "NeuralClaw Memory" in payload["hookSpecificOutput"]["additionalContext"]


def test_hook_silent_when_no_memory(fresh_db, monkeypatch, capsys):
    create_project("empty", "")
    monkeypatch.setenv("NEURALCLAW_CC_PROJECT", "empty")
    rc = hook.main([])
    assert rc == 0
    assert capsys.readouterr().out.strip() == ""


def test_scaffold_writes_and_is_idempotent(tmp_path):
    first = scaffold.install(tmp_path, project="demo", token_budget=1200)
    assert all(first.values())  # everything written on first run

    # Files contain the expected wiring.
    mcp = json.loads((tmp_path / ".mcp.json").read_text())
    assert mcp["mcpServers"]["neuralclaw-memory"]["command"] == "neuralclaw-cc-memory"
    settings = json.loads((tmp_path / ".claude" / "settings.json").read_text())
    cmds = [
        h["command"]
        for g in settings["hooks"]["SessionStart"]
        for h in g["hooks"]
    ]
    assert "neuralclaw-cc-hook" in cmds
    assert scaffold.CLAUDE_MD_MARKER in (tmp_path / "CLAUDE.md").read_text()

    # Second run changes nothing.
    second = scaffold.install(tmp_path, project="demo", token_budget=1200)
    assert not any(second.values())


def test_scaffold_merges_existing_mcp(tmp_path):
    (tmp_path / ".mcp.json").write_text(json.dumps({
        "mcpServers": {"other": {"command": "x"}}
    }))
    scaffold.install(tmp_path, with_hook=False, with_claude_md=False)
    data = json.loads((tmp_path / ".mcp.json").read_text())
    assert "other" in data["mcpServers"]
    assert "neuralclaw-memory" in data["mcpServers"]
