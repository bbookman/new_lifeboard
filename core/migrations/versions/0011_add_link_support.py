"""
Add link document type support to user_documents

This migration adds support for link documents by:
1. Adding a url column for storing link URLs
2. Updating the document_type constraint to allow 'link' type
"""

import sqlite3
import logging

logger = logging.getLogger(__name__)


def up(conn: sqlite3.Connection) -> None:
    """Apply the migration - add link document support"""
    logger.info("Adding link document support to user_documents...")
    
    # First, try to add the url column if it doesn't exist
    try:
        conn.execute("""
            ALTER TABLE user_documents 
            ADD COLUMN url TEXT
        """)
        logger.info("Added url column")
    except sqlite3.OperationalError as e:
        if "duplicate column" in str(e).lower():
            logger.info("URL column already exists")
        else:
            raise
    
    # SQLite doesn't support modifying constraints directly, so we need to recreate the table
    logger.info("Recreating table with updated constraint to support link document type...")
    
    conn.execute("""
        CREATE TABLE user_documents_new (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            document_type TEXT NOT NULL CHECK (document_type IN ('note', 'prompt', 'folder', 'link')),
            content_delta TEXT NOT NULL,  -- Quill Delta JSON format
            content_md TEXT NOT NULL,     -- Markdown version for search/LLM
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            path VARCHAR(500) DEFAULT '/' NOT NULL,
            is_folder BOOLEAN DEFAULT FALSE NOT NULL,
            url TEXT  -- URL for link documents
        )
    """)
    
    # Copy existing data
    conn.execute("""
        INSERT INTO user_documents_new 
        SELECT id, title, document_type, content_delta, content_md, 
               created_at, updated_at, path, is_folder, url
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
    conn.execute("CREATE INDEX IF NOT EXISTS idx_user_documents_type ON user_documents(document_type)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_user_documents_updated_at ON user_documents(updated_at)")
    
    # Recreate virtual directory indexes
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_documents_path 
        ON user_documents(path)
    """)
    
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_documents_folder_contents 
        ON user_documents(path, is_folder)
    """)
    
    
    # Create index for URL column (for link documents)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_documents_url 
        ON user_documents(url) WHERE url IS NOT NULL
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
    
    logger.info("Link document support added successfully")


def down(conn: sqlite3.Connection) -> None:
    """Rollback the migration - remove link document support"""
    logger.info("Removing link document support...")
    
    # Recreate table without link support and url column
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
    
    # Copy existing data (excluding link documents and url column)
    conn.execute("""
        INSERT INTO user_documents_new 
        SELECT id, user_id, title, document_type, content_delta, content_md, 
               created_at, updated_at, path, is_folder
        FROM user_documents
        WHERE document_type != 'link'
    """)
    
    # Drop triggers first
    conn.execute("DROP TRIGGER IF EXISTS user_documents_au")
    conn.execute("DROP TRIGGER IF EXISTS user_documents_ad")
    conn.execute("DROP TRIGGER IF EXISTS user_documents_ai")
    
    # Drop old table and rename new one
    conn.execute("DROP TABLE user_documents")
    conn.execute("ALTER TABLE user_documents_new RENAME TO user_documents")
    
    # Recreate indexes (excluding URL index)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_user_documents_user_id ON user_documents(user_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_user_documents_type ON user_documents(document_type)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_user_documents_updated_at ON user_documents(updated_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_user_documents_user_type ON user_documents(user_id, document_type)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_path ON user_documents(path)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_folder_contents ON user_documents(path, is_folder)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_user_path ON user_documents(user_id, path)")
    
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
    
    logger.info("Link document support removed")