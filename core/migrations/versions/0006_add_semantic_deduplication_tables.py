MIGRATION_ID = "0006_add_semantic_deduplication_tables"
CREATED_AT = "2025-01-15T00:00:00Z"

def up(connection):
    """Create tables for semantic deduplication system"""
    
    # Create semantic clusters table
    connection.execute("""
        CREATE TABLE IF NOT EXISTS semantic_clusters (
            id TEXT PRIMARY KEY,
            theme TEXT NOT NULL,
            canonical_line TEXT NOT NULL,
            confidence_score REAL NOT NULL CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0),
            frequency_count INTEGER NOT NULL CHECK (frequency_count > 0),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create bridge table linking lines to clusters
    connection.execute("""
        CREATE TABLE IF NOT EXISTS line_cluster_mapping (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_item_id TEXT NOT NULL,
            line_content TEXT NOT NULL,
            cluster_id TEXT NOT NULL,
            similarity_score REAL NOT NULL CHECK (similarity_score >= 0.0 AND similarity_score <= 1.0),
            speaker TEXT,
            line_timestamp TEXT,
            is_canonical BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (data_item_id) REFERENCES data_items(id) ON DELETE CASCADE,
            FOREIGN KEY (cluster_id) REFERENCES semantic_clusters(id) ON DELETE CASCADE
        )
    """)
    
    # Create indexes for performance
    connection.execute("CREATE INDEX IF NOT EXISTS idx_clusters_theme ON semantic_clusters(theme)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_clusters_frequency ON semantic_clusters(frequency_count DESC)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_clusters_confidence ON semantic_clusters(confidence_score DESC)")
    
    connection.execute("CREATE INDEX IF NOT EXISTS idx_line_mapping_item ON line_cluster_mapping(data_item_id)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_line_mapping_cluster ON line_cluster_mapping(cluster_id)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_line_mapping_canonical ON line_cluster_mapping(is_canonical)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_line_mapping_similarity ON line_cluster_mapping(similarity_score DESC)")
    
    # Create composite indexes for common queries
    connection.execute("CREATE INDEX IF NOT EXISTS idx_line_mapping_item_canonical ON line_cluster_mapping(data_item_id, is_canonical)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_line_mapping_cluster_canonical ON line_cluster_mapping(cluster_id, is_canonical)")

def down(connection):
    """Drop semantic deduplication tables"""
    connection.execute("DROP TABLE IF EXISTS line_cluster_mapping")
    connection.execute("DROP TABLE IF EXISTS semantic_clusters")