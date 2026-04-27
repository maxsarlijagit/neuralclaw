"""Migration v0.4.0: Add relevance_score and embeddings cache."""

import sqlite3

MIGRATION_SQL = """
-- Add relevance_score column to context_items
-- This column tracks contextual relevance based on staleness, confidence, usage
ALTER TABLE context_items ADD COLUMN relevance_score REAL DEFAULT 1.0 CHECK(relevance_score >= 0.0);

-- Create embeddings cache table for semantic search
CREATE TABLE IF NOT EXISTS embeddings_cache (
    id TEXT PRIMARY KEY,
    item_id TEXT REFERENCES context_items(id) ON DELETE CASCADE,
    text_hash TEXT NOT NULL,
    embedding BLOB NOT NULL,
    created_at INTEGER NOT NULL,
    UNIQUE(item_id, text_hash)
);

CREATE INDEX IF NOT EXISTS idx_emb_item ON embeddings_cache(item_id);
CREATE INDEX IF NOT EXISTS idx_emb_hash ON embeddings_cache(text_hash);

-- Update schema version
INSERT OR REPLACE INTO schema_version (version, applied_at) VALUES ('0.4.0', unixepoch('now'));
"""

def apply(connection: sqlite3.Connection) -> None:
    """Apply v0.4.0 migration."""
    cursor = connection.cursor()
    
    # Add relevance_score column (may fail if already exists)
    try:
        cursor.execute("ALTER TABLE context_items ADD COLUMN relevance_score REAL DEFAULT 1.0 CHECK(relevance_score >= 0.0)")
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    # Create embeddings cache table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS embeddings_cache (
            id TEXT PRIMARY KEY,
            item_id TEXT REFERENCES context_items(id) ON DELETE CASCADE,
            text_hash TEXT NOT NULL,
            embedding BLOB NOT NULL,
            created_at INTEGER NOT NULL,
            UNIQUE(item_id, text_hash)
        )
    """)
    
    # Create indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_emb_item ON embeddings_cache(item_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_emb_hash ON embeddings_cache(text_hash)")
    
    # Update schema version
    cursor.execute("INSERT OR REPLACE INTO schema_version (version, applied_at) VALUES ('0.4.0', unixepoch('now'))")