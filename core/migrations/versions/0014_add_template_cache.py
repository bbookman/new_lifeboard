"""
Add template cache table for performance optimization

This migration adds a template_cache table to store resolved template results
for improved performance when processing the same templates repeatedly.

Migration ID: 0014
Dependencies: 0013
"""

from typing import Any, Dict


def get_migration_info() -> Dict[str, Any]:
    """Get migration metadata"""
    return {
        "id": "0014",
        "name": "add_template_cache",
        "description": "Add template cache table for template processing performance",
        "dependencies": ["0013"],
    }


def upgrade(cursor) -> None:
    """Apply the migration"""

    # Create template_cache table
    cursor.execute("""
        CREATE TABLE template_cache (
            id TEXT PRIMARY KEY,
            template_hash TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            target_date TEXT NOT NULL,
            resolved_content TEXT NOT NULL,
            variables_resolved INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL
        )
    """)

    # Add indexes for performance
    cursor.execute("""
        CREATE INDEX idx_template_cache_hash_date 
        ON template_cache(template_hash, target_date)
    """)

    cursor.execute("""
        CREATE INDEX idx_template_cache_expires 
        ON template_cache(expires_at)
    """)

    print("✅ Created template_cache table with indexes")


def downgrade(cursor) -> None:
    """Rollback the migration"""

    # Drop indexes first
    cursor.execute("DROP INDEX IF EXISTS idx_template_cache_expires")
    cursor.execute("DROP INDEX IF EXISTS idx_template_cache_hash_date")

    # Drop table
    cursor.execute("DROP TABLE IF EXISTS template_cache")

    print("✅ Dropped template_cache table and indexes")
