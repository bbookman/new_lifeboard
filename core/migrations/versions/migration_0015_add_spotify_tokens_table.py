"""
Add Spotify tokens table for OAuth authentication

This migration creates the spotify_tokens table for storing user OAuth tokens
from Spotify, enabling user-specific data access instead of client credentials.

Migration ID: 0015
Dependencies: 0014
"""

from typing import Dict, Any


def get_migration_info() -> Dict[str, Any]:
    """Get migration metadata"""
    return {
        "id": "0015",
        "name": "add_spotify_tokens",
        "description": "Add spotify_tokens table for OAuth token storage",
        "dependencies": ["0014"]
    }


def upgrade(cursor) -> None:
    """Apply the migration"""
    
    # Create spotify_tokens table
    cursor.execute("""
        CREATE TABLE spotify_tokens (
            id INTEGER PRIMARY KEY,
            access_token TEXT NOT NULL,
            refresh_token TEXT,
            expires_at TIMESTAMP NOT NULL,
            scope TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            
            -- Constraints
            CONSTRAINT non_empty_access_token CHECK (length(trim(access_token)) > 0)
        )
    """)
    
    # Add indexes for performance
    cursor.execute("""
        CREATE INDEX idx_spotify_tokens_expires_at 
        ON spotify_tokens(expires_at)
    """)
    
    cursor.execute("""
        CREATE INDEX idx_spotify_tokens_updated_at 
        ON spotify_tokens(updated_at)
    """)
    
    print("✅ Created spotify_tokens table with indexes and constraints")


def downgrade(cursor) -> None:
    """Rollback the migration"""
    
    # Drop indexes first (if they exist)
    cursor.execute("DROP INDEX IF EXISTS idx_spotify_tokens_updated_at")
    cursor.execute("DROP INDEX IF EXISTS idx_spotify_tokens_expires_at")
    
    # Drop table
    cursor.execute("DROP TABLE IF EXISTS spotify_tokens")
    
    print("✅ Dropped spotify_tokens table and indexes")