"""Add prompt settings table migration"""

import sqlite3
from core.migrations import BaseMigration


class PromptSettingsMigration(BaseMigration):
    """Add prompt settings table for UI preferences"""
    
    @property
    def version(self) -> str:
        return "005_prompt_settings"
    
    @property
    def description(self) -> str:
        return "Add prompt settings table for storing user prompt preferences"
    
    def up(self, conn: sqlite3.Connection) -> None:
        """Create prompt settings table"""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS prompt_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                setting_key TEXT NOT NULL,
                prompt_document_id TEXT NOT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Add index for active settings lookup
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_prompt_settings_active 
            ON prompt_settings(setting_key, is_active)
        """)
