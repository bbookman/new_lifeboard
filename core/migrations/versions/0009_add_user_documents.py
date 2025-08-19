"""
Add user documents table for Notes & Prompts feature

This migration creates the infrastructure for user-generated documents
including notes and prompts with rich text editing capabilities.
"""

import sqlite3
import logging

logger = logging.getLogger(__name__)


def up(conn: sqlite3.Connection) -> None:
    """Apply the migration - create user documents tables"""
    logger.info("Creating user documents tables...")
    
    # Create main user_documents table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_documents (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            document_type TEXT NOT NULL CHECK (document_type IN ('note', 'prompt')),
            content_delta TEXT NOT NULL,  -- Quill Delta JSON format
            content_md TEXT NOT NULL,     -- Markdown version for search/LLM
            home_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create FTS5 virtual table for full-text search
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS user_documents_fts USING fts5(
            title,
            content_md,
            content=user_documents,
            content_rowid=id
        )
    """)
    
    # Create indexes for performance
    conn.execute("CREATE INDEX IF NOT EXISTS idx_user_documents_type ON user_documents(document_type)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_user_documents_updated_at ON user_documents(updated_at)")
    
    # Create triggers to keep FTS5 table in sync
    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS user_documents_ai AFTER INSERT ON user_documents BEGIN
            INSERT INTO user_documents_fts(rowid, title, content_md) 
            VALUES (NEW.rowid, NEW.title, NEW.content_md);
        END
    """)
    
    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS user_documents_ad AFTER DELETE ON user_documents BEGIN
            INSERT INTO user_documents_fts(user_documents_fts, rowid, title, content_md) 
            VALUES('delete', OLD.rowid, OLD.title, OLD.content_md);
        END
    """)
    
    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS user_documents_au AFTER UPDATE ON user_documents BEGIN
            INSERT INTO user_documents_fts(user_documents_fts, rowid, title, content_md) 
            VALUES('delete', OLD.rowid, OLD.title, OLD.content_md);
            INSERT INTO user_documents_fts(rowid, title, content_md) 
            VALUES (NEW.rowid, NEW.title, NEW.content_md);
        END
    """)
    
    logger.info("User documents tables created successfully")


def down(conn: sqlite3.Connection) -> None:
    """Rollback the migration - remove user documents tables"""
    logger.info("Dropping user documents tables...")
    
    # Drop triggers first
    conn.execute("DROP TRIGGER IF EXISTS user_documents_au")
    conn.execute("DROP TRIGGER IF EXISTS user_documents_ad")
    conn.execute("DROP TRIGGER IF EXISTS user_documents_ai")
    
    # Drop indexes
    conn.execute("DROP INDEX IF EXISTS idx_user_documents_updated_at")
    conn.execute("DROP INDEX IF EXISTS idx_user_documents_type")
    
    # Drop tables
    conn.execute("DROP TABLE IF EXISTS user_documents_fts")
    conn.execute("DROP TABLE IF EXISTS user_documents")
    
    logger.info("User documents tables dropped successfully")