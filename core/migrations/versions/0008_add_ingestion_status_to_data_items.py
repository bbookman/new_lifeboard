MIGRATION_ID = "0008_add_ingestion_status_to_data_items"
CREATED_AT = "2025-08-14T10:00:00Z"

def up(connection):
    """Add ingestion_status column to data_items table"""

    connection.execute("""
        ALTER TABLE data_items 
        ADD COLUMN ingestion_status TEXT DEFAULT 'complete' 
        CHECK (ingestion_status IN ('partial', 'complete', 'failed'))
    """)

    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_data_items_ingestion_status 
        ON data_items(ingestion_status)
    """)

def down(connection):
    """Remove ingestion_status tracking from data_items table"""

    connection.execute("DROP INDEX IF EXISTS idx_data_items_ingestion_status")

    # SQLite doesn't support DROP COLUMN easily.
    # The common workaround is to recreate the table and copy data,
    # which is too complex and risky for a simple downgrade.
    # We will leave the column in place on downgrade.
