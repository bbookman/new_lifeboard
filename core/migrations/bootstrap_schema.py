"""
Consolidated Database Schema for Lifeboard

This file contains the complete database schema that replaces all individual
migration files. Designed for test/development environments where the database
is frequently deleted and rebuilt.

Schema includes:
- Core data storage (data_items, data_sources)  
- Chat functionality (chat_messages)
- Weather data (weather)
- News data (news)
- Limitless integration (limitless)
- User documents with FTS5 search (user_documents, user_documents_fts)
- Semantic deduplication (semantic_clusters, line_cluster_mapping)
- System settings and migration tracking
"""

import sqlite3
import logging

logger = logging.getLogger(__name__)


def create_complete_schema(conn: sqlite3.Connection) -> None:
    """Create the complete Lifeboard database schema"""
    logger.info("Creating complete Lifeboard database schema...")
    
    # ========================================
    # CORE SYSTEM TABLES
    # ========================================
    
    # System settings table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS system_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Migration tracking table (simplified)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS migrations (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Data sources registry
    conn.execute("""
        CREATE TABLE IF NOT EXISTS data_sources (
            namespace TEXT PRIMARY KEY,
            source_type TEXT NOT NULL,
            metadata TEXT,
            item_count INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT TRUE,
            last_synced TIMESTAMP,
            first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # ========================================
    # UNIFIED DATA STORAGE
    # ========================================
    
    # Main data storage table with all columns from migrations
    conn.execute("""
        CREATE TABLE IF NOT EXISTS data_items (
            id TEXT PRIMARY KEY,
            namespace TEXT NOT NULL,
            source_id TEXT NOT NULL,
            content TEXT,
            metadata TEXT,
            embedding_status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            days_date TEXT NOT NULL,
            semantic_status TEXT DEFAULT 'pending' CHECK (semantic_status IN ('pending', 'processing', 'completed', 'failed')),
            semantic_processed_at TIMESTAMP,
            processing_priority INTEGER DEFAULT 1,
            ingestion_status TEXT DEFAULT 'complete' CHECK (ingestion_status IN ('partial', 'complete', 'failed'))
        )
    """)
    
    # ========================================
    # CHAT FUNCTIONALITY
    # ========================================
    
    # Chat messages table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_message TEXT NOT NULL,
            assistant_response TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # ========================================
    # SOURCE-SPECIFIC TABLES
    # ========================================
    
    # Weather data cache
    conn.execute("""
        CREATE TABLE IF NOT EXISTS weather (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            days_date TEXT NOT NULL,
            response_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # News headlines cache for deduplication
    conn.execute("""
        CREATE TABLE IF NOT EXISTS news (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            link TEXT,
            snippet TEXT,
            days_date TEXT NOT NULL,
            thumbnail_url TEXT,
            published_datetime_utc TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Limitless lifelog data for specialized processing
    conn.execute("""
        CREATE TABLE IF NOT EXISTS limitless (
            id TEXT PRIMARY KEY,
            lifelog_id TEXT NOT NULL UNIQUE,
            title TEXT,
            start_time TEXT,
            end_time TEXT,
            is_starred BOOLEAN DEFAULT FALSE,
            updated_at_api TEXT,
            processed_content TEXT,
            raw_data TEXT,
            days_date TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # ========================================
    # SEMANTIC DEDUPLICATION SYSTEM
    # ========================================
    
    # Semantic clusters table
    conn.execute("""
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
    
    # Bridge table linking lines to clusters
    conn.execute("""
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
    
    # ========================================
    # USER DOCUMENTS SYSTEM
    # ========================================
    
    # Main user documents table (no user_id - single user system)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_documents (
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
    
    # FTS5 virtual table for full-text search
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS user_documents_fts USING fts5(
            title,
            content_md,
            content=user_documents,
            content_rowid=id
        )
    """)
    
    # ========================================
    # LLM PROMPT MANAGEMENT SYSTEM
    # ========================================
    
    # Prompt settings table for LLM prompt management
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
    
    # Generated summaries table for LLM content caching
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
    
    logger.info("Database tables created successfully")


def create_all_indexes(conn: sqlite3.Connection) -> None:
    """Create all database indexes for performance"""
    logger.info("Creating database indexes...")
    
    # ========================================
    # DATA_ITEMS INDEXES
    # ========================================
    
    # Core data_items indexes
    conn.execute("CREATE INDEX IF NOT EXISTS idx_data_items_namespace ON data_items(namespace)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_data_items_embedding_status ON data_items(embedding_status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_data_items_updated_at ON data_items(updated_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_data_items_days_date ON data_items(days_date)")
    
    # Semantic processing indexes
    conn.execute("CREATE INDEX IF NOT EXISTS idx_data_items_semantic_status ON data_items(semantic_status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_data_items_day_semantic_status ON data_items(days_date, semantic_status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_data_items_namespace_semantic_status ON data_items(namespace, semantic_status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_semantic_status_date ON data_items(semantic_status, days_date)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_processed_at ON data_items(semantic_processed_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_semantic_queue ON data_items(semantic_status, processing_priority, days_date, created_at)")
    
    # Ingestion status indexes
    conn.execute("CREATE INDEX IF NOT EXISTS idx_data_items_ingestion_status ON data_items(ingestion_status)")
    
    # ========================================
    # CHAT INDEXES
    # ========================================
    
    conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_messages_timestamp ON chat_messages(timestamp)")
    
    # ========================================
    # SOURCE-SPECIFIC INDEXES
    # ========================================
    
    # Weather indexes
    conn.execute("CREATE INDEX IF NOT EXISTS idx_weather_days_date ON weather(days_date)")
    
    # News indexes
    conn.execute("CREATE INDEX IF NOT EXISTS idx_news_days_date ON news(days_date)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_news_title ON news(title)")
    
    # Limitless indexes
    conn.execute("CREATE INDEX IF NOT EXISTS idx_limitless_days_date ON limitless(days_date)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_limitless_lifelog_id ON limitless(lifelog_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_limitless_start_time ON limitless(start_time)")
    
    # ========================================
    # SEMANTIC DEDUPLICATION INDEXES
    # ========================================
    
    # Semantic clusters indexes
    conn.execute("CREATE INDEX IF NOT EXISTS idx_clusters_theme ON semantic_clusters(theme)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_clusters_frequency ON semantic_clusters(frequency_count DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_clusters_confidence ON semantic_clusters(confidence_score DESC)")
    
    # Line cluster mapping indexes
    conn.execute("CREATE INDEX IF NOT EXISTS idx_line_mapping_item ON line_cluster_mapping(data_item_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_line_mapping_cluster ON line_cluster_mapping(cluster_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_line_mapping_canonical ON line_cluster_mapping(is_canonical)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_line_mapping_similarity ON line_cluster_mapping(similarity_score DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_line_mapping_item_canonical ON line_cluster_mapping(data_item_id, is_canonical)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_line_mapping_cluster_canonical ON line_cluster_mapping(cluster_id, is_canonical)")
    
    # ========================================
    # USER DOCUMENTS INDEXES
    # ========================================
    
    # User documents indexes (consolidated performance indexes from 0013)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_user_documents_type ON user_documents(document_type)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_user_documents_updated_at ON user_documents(updated_at DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_user_documents_type_updated ON user_documents(document_type, updated_at DESC)")
    
    # Virtual directory indexes
    conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_path ON user_documents(path)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_folder_contents ON user_documents(path, is_folder)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_is_folder ON user_documents(is_folder)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_folder_type ON user_documents(path, is_folder, document_type)")
    
    # URL index for link documents
    conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_url ON user_documents(url) WHERE url IS NOT NULL")
    
    # ========================================
    # LLM PROMPT MANAGEMENT INDEXES
    # ========================================
    
    # Prompt settings indexes
    conn.execute("CREATE INDEX IF NOT EXISTS idx_prompt_settings_key ON prompt_settings(setting_key)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_prompt_settings_active ON prompt_settings(is_active)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_prompt_settings_document ON prompt_settings(prompt_document_id)")
    
    # Generated summaries indexes
    conn.execute("CREATE INDEX IF NOT EXISTS idx_generated_summaries_date ON generated_summaries(days_date)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_generated_summaries_active ON generated_summaries(is_active)")
    
    logger.info("Database indexes created successfully")


def create_triggers(conn: sqlite3.Connection) -> None:
    """Create all database triggers"""
    logger.info("Creating database triggers...")
    
    # User documents FTS5 sync triggers
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
    
    # Prompt settings updated_at trigger
    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS prompt_settings_update_timestamp 
        AFTER UPDATE ON prompt_settings
        BEGIN
            UPDATE prompt_settings 
            SET updated_at = CURRENT_TIMESTAMP 
            WHERE id = NEW.id;
        END
    """)
    
    logger.info("Database triggers created successfully")


def bootstrap_database(conn: sqlite3.Connection) -> None:
    """Bootstrap complete database schema"""
    try:
        # Create all tables
        create_complete_schema(conn)
        
        # Create all indexes
        create_all_indexes(conn)
        
        # Create all triggers
        create_triggers(conn)
        
        # Mark bootstrap as complete
        conn.execute("""
            INSERT OR REPLACE INTO migrations (name)
            VALUES ('bootstrap_schema_complete')
        """)
        
        conn.commit()
        logger.info("Database bootstrap completed successfully")
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Database bootstrap failed: {e}")
        raise


def is_database_initialized(conn: sqlite3.Connection) -> bool:
    """Check if database has been bootstrapped"""
    try:
        cursor = conn.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='migrations'
        """)
        if not cursor.fetchone():
            return False
            
        cursor = conn.execute("""
            SELECT 1 FROM migrations 
            WHERE name='bootstrap_schema_complete'
        """)
        return cursor.fetchone() is not None
        
    except Exception:
        return False