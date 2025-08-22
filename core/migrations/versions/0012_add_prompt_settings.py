"""
Add prompt_settings table for LLM prompt management

This migration adds support for LLM prompt settings by:
1. Creating prompt_settings table to track selected prompts
2. Adding indexes for efficient lookups
3. Supporting future prompt applications beyond daily summaries
"""

import logging
import sqlite3

logger = logging.getLogger(__name__)


def up(conn: sqlite3.Connection) -> None:
    """Apply the migration - add prompt_settings table"""
    logger.info("Adding prompt_settings table for LLM prompt management...")

    # Create prompt_settings table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS prompt_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            setting_key TEXT NOT NULL UNIQUE,  -- e.g., 'daily_summary_prompt'
            prompt_document_id TEXT,           -- References user_documents.id
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (prompt_document_id) REFERENCES user_documents(id) ON DELETE SET NULL
        )
    """)

    # Create indexes for efficient lookups
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_prompt_settings_key 
        ON prompt_settings(setting_key)
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_prompt_settings_active 
        ON prompt_settings(is_active)
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_prompt_settings_document 
        ON prompt_settings(prompt_document_id)
    """)

    # Create trigger to update updated_at timestamp
    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS prompt_settings_update_timestamp 
        AFTER UPDATE ON prompt_settings
        BEGIN
            UPDATE prompt_settings 
            SET updated_at = CURRENT_TIMESTAMP 
            WHERE id = NEW.id;
        END
    """)

    # Create generated_summaries table for LLM content caching
    conn.execute("""
        CREATE TABLE IF NOT EXISTS generated_summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            days_date TEXT NOT NULL,
            content TEXT NOT NULL,
            prompt_used TEXT,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create indexes for generated_summaries
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_generated_summaries_date 
        ON generated_summaries(days_date)
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_generated_summaries_active 
        ON generated_summaries(is_active)
    """)

    logger.info("prompt_settings and generated_summaries tables created successfully")
