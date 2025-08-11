MIGRATION_ID = "0007_add_semantic_status_tracking"
CREATED_AT = "2025-01-15T12:00:00Z"

def up(connection):
    """Add semantic_status column to data_items table for queue management"""
    
    # Add semantic_status column to data_items table
    connection.execute("""
        ALTER TABLE data_items 
        ADD COLUMN semantic_status TEXT DEFAULT 'pending' 
        CHECK (semantic_status IN ('pending', 'processing', 'completed', 'failed'))
    """)
    
    # Add index for performance on semantic status queries
    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_data_items_semantic_status 
        ON data_items(semantic_status)
    """)
    
    # Add composite index for efficient day + status queries
    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_data_items_day_semantic_status 
        ON data_items(days_date, semantic_status)
    """)
    
    # Add namespace + status index for batch processing
    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_data_items_namespace_semantic_status 
        ON data_items(namespace, semantic_status)
    """)

def down(connection):
    """Remove semantic_status tracking from data_items table"""
    
    # Drop indexes first
    connection.execute("DROP INDEX IF EXISTS idx_data_items_semantic_status")
    connection.execute("DROP INDEX IF EXISTS idx_data_items_day_semantic_status") 
    connection.execute("DROP INDEX IF EXISTS idx_data_items_namespace_semantic_status")
    
    # Remove column (SQLite doesn't support DROP COLUMN directly, so we'd need to recreate table)
    # For now, just set all values to NULL
    connection.execute("UPDATE data_items SET semantic_status = NULL")