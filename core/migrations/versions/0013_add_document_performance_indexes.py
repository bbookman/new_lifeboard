"""
Add performance indexes for document queries

This migration adds database indexes to optimize common document queries:
1. Index on document_type for fast filtering by type (note, prompt, etc.)
2. Index on path for fast folder-based queries
3. Index on is_folder for quick folder/document distinction
4. Composite index on (document_type, updated_at) for fast sorted listings
5. Index on updated_at for general sorting performance
"""

import sqlite3
import logging

logger = logging.getLogger(__name__)


def up(conn: sqlite3.Connection) -> None:
    """Apply the migration - add performance indexes"""
    logger.info("Adding performance indexes for document queries...")
    
    # Index on document_type for fast type filtering (note, prompt, etc.)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_user_documents_type 
        ON user_documents(document_type)
    """)
    
    # Index on path for fast folder-based queries
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_user_documents_path 
        ON user_documents(path)
    """)
    
    # Index on is_folder for quick folder/document distinction
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_user_documents_is_folder 
        ON user_documents(is_folder)
    """)
    
    # Composite index for fast sorted listings by type
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_user_documents_type_updated 
        ON user_documents(document_type, updated_at DESC)
    """)
    
    # Index on updated_at for general sorting performance
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_user_documents_updated_at 
        ON user_documents(updated_at DESC)
    """)
    
    # Composite index for folder content queries
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_user_documents_folder_type 
        ON user_documents(path, is_folder, document_type)
    """)
    
    logger.info("Performance indexes for documents created successfully")


def down(conn: sqlite3.Connection) -> None:
    """Rollback the migration - remove performance indexes"""
    logger.info("Rolling back performance indexes for document queries...")
    
    # Drop all created indexes
    indexes_to_drop = [
        "idx_user_documents_type",
        "idx_user_documents_path", 
        "idx_user_documents_is_folder",
        "idx_user_documents_type_updated",
        "idx_user_documents_updated_at",
        "idx_user_documents_folder_type"
    ]
    
    for index_name in indexes_to_drop:
        try:
            conn.execute(f"DROP INDEX IF EXISTS {index_name}")
            logger.debug(f"Dropped index: {index_name}")
        except Exception as e:
            logger.warning(f"Error dropping index {index_name}: {e}")
    
    logger.info("Performance indexes rollback completed")