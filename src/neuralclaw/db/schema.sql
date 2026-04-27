-- NeuralClaw Schema v0.1
-- Single source of truth for database structure

-- Projects
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    status TEXT DEFAULT 'active' CHECK(status IN ('active', 'archived', 'stale')),
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    archived_at INTEGER
);

-- Context items
CREATE TABLE IF NOT EXISTS context_items (
    id TEXT PRIMARY KEY,
    project_id TEXT REFERENCES projects(id) ON DELETE CASCADE,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    type TEXT DEFAULT 'note' CHECK(type IN ('note', 'decision', 'error', 'variable', 'preference')),
    state TEXT DEFAULT 'active' CHECK(state IN ('active', 'stale', 'deprecated', 'archived', 'conflicting', 'verified', 'unknown', 'old_school')),
    tags TEXT,  -- JSON array stored as text
    sources TEXT,  -- JSON array of source refs
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    stale_after INTEGER,  -- Unix timestamp; NULL = never stale
    confidence REAL DEFAULT 1.0 CHECK(confidence >= 0.0 AND confidence <= 1.0),
    relevance_score REAL DEFAULT 1.0 CHECK(relevance_score >= 0.0),
    UNIQUE(project_id, key)
);

-- Context links (relationships between context items)
CREATE TABLE IF NOT EXISTS context_links (
    id TEXT PRIMARY KEY,
    from_item_id TEXT REFERENCES context_items(id) ON DELETE CASCADE,
    to_item_id TEXT REFERENCES context_items(id) ON DELETE CASCADE,
    link_type TEXT NOT NULL CHECK(link_type IN ('relates_to', 'depends_on', 'supersedes', 'contradicts')),
    created_at INTEGER NOT NULL
);

-- Errors log
CREATE TABLE IF NOT EXISTS errors (
    id TEXT PRIMARY KEY,
    project_id TEXT REFERENCES projects(id) ON DELETE CASCADE,
    error_type TEXT NOT NULL,
    message TEXT NOT NULL,
    stack_trace TEXT,
    resolved INTEGER DEFAULT 0 CHECK(resolved IN (0, 1)),
    resolved_at INTEGER,
    created_at INTEGER NOT NULL
);

-- Decisions log
CREATE TABLE IF NOT EXISTS decisions (
    id TEXT PRIMARY KEY,
    project_id TEXT REFERENCES projects(id) ON DELETE CASCADE,
    decision TEXT NOT NULL,
    rationale TEXT,
    decided_by TEXT DEFAULT 'human' CHECK(decided_by IN ('human', 'agent', 'system')),
    created_at INTEGER NOT NULL,
    expires_at INTEGER  -- Unix timestamp; NULL = never expires
);

-- Usage logs
CREATE TABLE IF NOT EXISTS usage_logs (
    id TEXT PRIMARY KEY,
    project_id TEXT REFERENCES projects(id) ON DELETE SET NULL,
    action TEXT NOT NULL CHECK(action IN ('search', 'add', 'update', 'delete', 'export', 'init', 'vault')),
    query TEXT,
    results_count INTEGER,
    tokens_used INTEGER,
    adapter TEXT,
    created_at INTEGER NOT NULL
);

-- Model profiles (Train Room output)
CREATE TABLE IF NOT EXISTS model_profiles (
    id TEXT PRIMARY KEY,
    model_id TEXT NOT NULL UNIQUE CHECK(model_id IN ('chatgpt', 'claude', 'deepseek', 'openclaw', 'generic')),
    communication_style TEXT DEFAULT 'detailed' CHECK(communication_style IN ('brief', 'detailed', 'technical')),
    preferred_length TEXT DEFAULT 'medium' CHECK(preferred_length IN ('short', 'medium', 'long')),
    format_preference TEXT DEFAULT 'markdown' CHECK(format_preference IN ('markdown', 'plain', 'structured')),
    tone TEXT DEFAULT 'casual' CHECK(tone IN ('formal', 'casual', 'technical')),
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);

-- FreshApple snapshots
CREATE TABLE IF NOT EXISTS fresh_apple (
    id TEXT PRIMARY KEY,
    project_id TEXT REFERENCES projects(id) ON DELETE CASCADE UNIQUE,
    content TEXT NOT NULL,  -- Markdown content
    generated_at INTEGER NOT NULL,
    auto_refresh INTEGER DEFAULT 1 CHECK(auto_refresh IN (0, 1))
);

-- Vault (encrypted secrets metadata - values stored encrypted in vault.db)
CREATE TABLE IF NOT EXISTS vault_entries (
    id TEXT PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,  -- Name of the secret (e.g. OPENAI_API_KEY)
    value_hash TEXT,  -- SHA256 hash to verify without exposing
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);

-- Schema version for migrations
CREATE TABLE IF NOT EXISTS schema_version (
    version TEXT PRIMARY KEY,
    applied_at INTEGER NOT NULL
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_context_project ON context_items(project_id);
CREATE INDEX IF NOT EXISTS idx_context_state ON context_items(state);
CREATE INDEX IF NOT EXISTS idx_context_stale ON context_items(stale_after);
CREATE INDEX IF NOT EXISTS idx_context_type ON context_items(type);
CREATE INDEX IF NOT EXISTS idx_context_key ON context_items(key);
CREATE INDEX IF NOT EXISTS idx_errors_project ON errors(project_id);
CREATE INDEX IF NOT EXISTS idx_errors_resolved ON errors(resolved);
CREATE INDEX IF NOT EXISTS idx_decisions_project ON decisions(project_id);
CREATE INDEX IF NOT EXISTS idx_fresh_project ON fresh_apple(project_id);
CREATE INDEX IF NOT EXISTS idx_usage_project ON usage_logs(project_id);
CREATE INDEX IF NOT EXISTS idx_usage_created ON usage_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_links_from ON context_links(from_item_id);
CREATE INDEX IF NOT EXISTS idx_links_to ON context_links(to_item_id);

-- Full-text search virtual table
CREATE VIRTUAL TABLE IF NOT EXISTS context_fts USING fts5(
    key,
    value,
    content='context_items',
    content_rowid='rowid'
);

-- Triggers to keep FTS in sync
CREATE TRIGGER IF NOT EXISTS context_fts_insert AFTER INSERT ON context_items BEGIN
    INSERT INTO context_fts(rowid, key, value) VALUES (new.rowid, new.key, new.value);
END;

CREATE TRIGGER IF NOT EXISTS context_fts_delete AFTER DELETE ON context_items BEGIN
    INSERT INTO context_fts(context_fts, rowid, key, value) VALUES('delete', old.rowid, old.key, old.value);
END;

CREATE TRIGGER IF NOT EXISTS context_fts_update AFTER UPDATE ON context_items BEGIN
    INSERT INTO context_fts(context_fts, rowid, key, value) VALUES('delete', old.rowid, old.key, old.value);
    INSERT INTO context_fts(rowid, key, value) VALUES (new.rowid, new.key, new.value);
END;

-- Embeddings cache for semantic search
CREATE TABLE IF NOT EXISTS embeddings_cache (
    id TEXT PRIMARY KEY,
    item_id TEXT REFERENCES context_items(id) ON DELETE CASCADE,
    text_hash TEXT NOT NULL,  -- SHA256 of the text that was embedded
    embedding BLOB NOT NULL,  -- Pickled numpy array or JSON list
    created_at INTEGER NOT NULL,
    UNIQUE(item_id, text_hash)
);

CREATE INDEX IF NOT EXISTS idx_emb_item ON embeddings_cache(item_id);
CREATE INDEX IF NOT EXISTS idx_emb_hash ON embeddings_cache(text_hash);

-- Record schema version
INSERT OR REPLACE INTO schema_version (version, applied_at) VALUES ('0.4.0', unixepoch('now'));