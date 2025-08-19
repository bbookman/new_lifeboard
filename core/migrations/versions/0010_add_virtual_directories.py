"""
Add virtual directory support to user_documents

This migration adds support for virtual directories using materialized path model.
Adds path and is_folder columns to enable hierarchical organization of documents.
Also updates the CHECK constraint to allow 'folder' document type.
"""

import sqlite3
import logging

logger = logging.getLogger(__name__)


def up(conn: sqlite3.Connection) -> None:
    """Apply the migration - add virtual directory support"""
    logger.info("Adding virtual directory support to user_documents...")
    
    # SQLite doesn't support modifying constraints directly, so we need to recreate the table
    # First, try to add new columns to existing table if they don't exist
    try:
        conn.execute("""
            ALTER TABLE user_documents 
            ADD COLUMN path VARCHAR(500) DEFAULT '/' NOT NULL
        """)
        logger.info("Added path column")
    except sqlite3.OperationalError as e:
        if "duplicate column" in str(e).lower():
            logger.info("Path column already exists")
        else:
            raise
    
    try:
        conn.execute("""
            ALTER TABLE user_documents 
            ADD COLUMN is_folder BOOLEAN DEFAULT FALSE NOT NULL
        """)
        logger.info("Added is_folder column")
    except sqlite3.OperationalError as e:
        if "duplicate column" in str(e).lower():
            logger.info("is_folder column already exists")
        else:
            raise
    
    # Now recreate the table with updated constraint to allow 'folder' document type
    logger.info("Recreating table with updated constraint...")
    
    conn.execute("""
        CREATE TABLE user_documents_new (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL DEFAULT 'default_user',
            title TEXT NOT NULL,
            document_type TEXT NOT NULL CHECK (document_type IN ('note', 'prompt', 'folder')),
            content_delta TEXT NOT NULL,  -- Quill Delta JSON format
            content_md TEXT NOT NULL,     -- Markdown version for search/LLM
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            path VARCHAR(500) DEFAULT '/' NOT NULL,
            is_folder BOOLEAN DEFAULT FALSE NOT NULL
        )
    """)
    
    # Copy existing data
    conn.execute("""
        INSERT INTO user_documents_new 
        SELECT id, user_id, title, document_type, content_delta, content_md, 
               created_at, updated_at, path, is_folder
        FROM user_documents
    """)
    
    # Drop triggers first
    conn.execute("DROP TRIGGER IF EXISTS user_documents_au")
    conn.execute("DROP TRIGGER IF EXISTS user_documents_ad")
    conn.execute("DROP TRIGGER IF EXISTS user_documents_ai")
    
    # Drop old table and rename new one
    conn.execute("DROP TABLE user_documents")
    conn.execute("ALTER TABLE user_documents_new RENAME TO user_documents")
    
    # Recreate all indexes
    conn.execute("CREATE INDEX IF NOT EXISTS idx_user_documents_user_id ON user_documents(user_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_user_documents_type ON user_documents(document_type)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_user_documents_updated_at ON user_documents(updated_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_user_documents_user_type ON user_documents(user_id, document_type)")
    
    # Create new virtual directory indexes
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_documents_path 
        ON user_documents(path)
    """)
    
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_documents_folder_contents 
        ON user_documents(path, is_folder)
    """)
    
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_documents_user_path 
        ON user_documents(user_id, path)
    """)
    
    # Recreate triggers
    conn.execute("""
        CREATE TRIGGER user_documents_ai AFTER INSERT ON user_documents BEGIN
            INSERT INTO user_documents_fts(rowid, title, content_md) 
            VALUES (NEW.rowid, NEW.title, NEW.content_md);
        END
    """)
    
    conn.execute("""
        CREATE TRIGGER user_documents_ad AFTER DELETE ON user_documents BEGIN
            INSERT INTO user_documents_fts(user_documents_fts, rowid, title, content_md) 
            VALUES('delete', OLD.rowid, OLD.title, OLD.content_md);
        END
    """)
    
    conn.execute("""
        CREATE TRIGGER user_documents_au AFTER UPDATE ON user_documents BEGIN
            INSERT INTO user_documents_fts(user_documents_fts, rowid, title, content_md) 
            VALUES('delete', OLD.rowid, OLD.title, OLD.content_md);
            INSERT INTO user_documents_fts(rowid, title, content_md) 
            VALUES (NEW.rowid, NEW.title, NEW.content_md);
        END
    """)
    
    logger.info("Virtual directory support added successfully")


def down(conn: sqlite3.Connection) -> None:
    """Rollback the migration - remove virtual directory support"""
    logger.info("Removing virtual directory support...")
    
    # Drop virtual directory indexes
    conn.execute("DROP INDEX IF EXISTS idx_documents_path")
    conn.execute("DROP INDEX IF EXISTS idx_documents_folder_contents") 
    conn.execute("DROP INDEX IF EXISTS idx_documents_user_path")
    
    # Note: SQLite doesn't support DROP COLUMN directly
    # This would require recreating the table again, which is complex
    # For now, we'll leave the columns but they won't be used
    logger.warning("SQLite doesn't support DROP COLUMN. Columns path and is_folder will remain but be unused.")
    
    logger.info("Virtual directory support removed")