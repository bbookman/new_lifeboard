"""
Unified Database Service for Lifeboard

Single-file database initialization and management system that creates
the complete schema in one operation without complex migration systems.
"""

import sqlite3
import json
import os
import logging
from typing import List, Dict, Optional, Any
from contextlib import contextmanager
from datetime import datetime, timezone
import pytz

from .json_utils import JSONMetadataParser, DatabaseRowParser

logger = logging.getLogger(__name__)


class UnifiedDatabaseService:
    """Unified database service with complete schema creation"""
    
    def __init__(self, db_path: str = "lifeboard.db"):
        self.db_path = db_path
        self._init_database()
    
    @contextmanager
    def get_connection(self):
        """Get database connection with proper setup"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        # Enable foreign key constraints
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
        finally:
            conn.close()
    
    def _init_database(self):
        """Initialize database with complete schema in single operation"""
        logger.info("Initializing Lifeboard database with unified schema...")
        
        try:
            with self.get_connection() as conn:
                # Check if already initialized
                if self._is_database_initialized(conn):
                    logger.info("Database already initialized")
                    return
                
                # Create complete schema
                self._create_complete_schema(conn)
                self._create_all_indexes(conn)
                self._create_triggers(conn)
                
                # Mark as initialized
                conn.execute("""
                    INSERT OR REPLACE INTO migrations (name)
                    VALUES ('unified_schema_complete')
                """)
                
                conn.commit()
                logger.info("Database initialization completed successfully")
                
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            raise RuntimeError(f"Database initialization failed: {e}")
    
    def _is_database_initialized(self, conn: sqlite3.Connection) -> bool:
        """Check if database has been initialized"""
        try:
            cursor = conn.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='migrations'
            """)
            if not cursor.fetchone():
                return False
                
            cursor = conn.execute("""
                SELECT 1 FROM migrations 
                WHERE name IN ('unified_schema_complete', 'bootstrap_schema_complete')
            """)
            return cursor.fetchone() is not None
            
        except Exception:
            return False
    
    def _create_complete_schema(self, conn: sqlite3.Connection) -> None:
        """Create complete database schema with all tables"""
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
        
        # Migration tracking table
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
        
        # Main data storage table with all columns
        conn.execute("""
            CREATE TABLE IF NOT EXISTS data_items (
                id TEXT PRIMARY KEY,
                namespace TEXT NOT NULL,
                source_id TEXT NOT NULL,
                content TEXT,
                metadata TEXT,
                embedding_status TEXT DEFAULT 'pending',
                speaker_label_status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                days_date TEXT NOT NULL,
                semantic_status TEXT DEFAULT 'pending' CHECK (semantic_status IN ('pending', 'processing', 'completed', 'failed')),
                semantic_processed_at TIMESTAMP,
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
                speaker_labeled_content TEXT,
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
        
        # Main user documents table
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
        
        # ========================================
        # TEMPLATE SYSTEM
        # ========================================
        
        # Template cache table for performance optimization
        conn.execute("""
            CREATE TABLE IF NOT EXISTS template_cache (
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
        
        logger.info("All database tables created successfully")
    
    def _create_all_indexes(self, conn: sqlite3.Connection) -> None:
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
        conn.execute("CREATE INDEX IF NOT EXISTS idx_data_items_speaker_status ON data_items(speaker_label_status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_data_items_namespace_speaker_status ON data_items(namespace, speaker_label_status)")
        
        # Semantic processing indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_data_items_semantic_status ON data_items(semantic_status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_data_items_day_semantic_status ON data_items(days_date, semantic_status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_data_items_namespace_semantic_status ON data_items(namespace, semantic_status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_semantic_status_date ON data_items(semantic_status, days_date)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_processed_at ON data_items(semantic_processed_at)")

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
        conn.execute("CREATE INDEX IF NOT EXISTS idx_limitless_speaker_labeled ON limitless(lifelog_id) WHERE speaker_labeled_content IS NOT NULL")
        
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
        
        # User documents indexes
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
        
        # ========================================
        # TEMPLATE SYSTEM INDEXES
        # ========================================
        
        # Template cache indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_template_cache_hash_date ON template_cache(template_hash, target_date)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_template_cache_expires ON template_cache(expires_at)")
        
        logger.info("All database indexes created successfully")
    
    def _create_triggers(self, conn: sqlite3.Connection) -> None:
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
        
        logger.info("All database triggers created successfully")
    
    # ========================================
    # DATABASE OPERATIONS (same as original DatabaseService)
    # ========================================
    
    def store_data_item(self, id: str, namespace: str, source_id: str, 
                       content: str, metadata: Dict = None, days_date: str = None,
                       ingestion_status: str = 'complete'):
        """Store data item with namespaced ID"""
        with self.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO data_items 
                (id, namespace, source_id, content, metadata, days_date, updated_at, ingestion_status)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
            """, (id, namespace, source_id, content, 
                  JSONMetadataParser.serialize_metadata(metadata), days_date, ingestion_status))
            conn.commit()
    
    def get_data_items_by_ids(self, ids: List[str]) -> List[Dict]:
        """Batch fetch data items by namespaced IDs"""
        if not ids:
            return []
        
        placeholders = ','.join('?' * len(ids))
        with self.get_connection() as conn:
            cursor = conn.execute(f"""
                SELECT id, namespace, source_id, content, metadata, days_date, created_at, updated_at
                FROM data_items 
                WHERE id IN ({placeholders})
                ORDER BY updated_at DESC
            """, ids)
            
            return DatabaseRowParser.parse_rows_with_metadata(
                [dict(row) for row in cursor.fetchall()]
            )
    
    def get_data_items_by_namespace(self, namespace: str, limit: int = 100) -> List[Dict]:
        """Get data items for a specific namespace"""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT id, namespace, source_id, content, metadata, days_date, created_at, updated_at
                FROM data_items 
                WHERE namespace = ?
                ORDER BY updated_at DESC
                LIMIT ?
            """, (namespace, limit))
            
            return DatabaseRowParser.parse_rows_with_metadata(
                [dict(row) for row in cursor.fetchall()]
            )
    
    def update_embedding_status(self, id: str, status: str):
        """Update embedding status for a data item"""
        with self.get_connection() as conn:
            conn.execute("""
                UPDATE data_items 
                SET embedding_status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (status, id))
            conn.commit()

    def update_ingestion_status(self, item_id: str, status: str):
        """Update ingestion status for a data item"""
        with self.get_connection() as conn:
            conn.execute("""
                UPDATE data_items
                SET ingestion_status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (status, item_id))
            conn.commit()
    
    def get_pending_embeddings(self, limit: int = 100) -> List[Dict]:
        """Get data items that need embedding"""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT id, namespace, source_id, content, metadata
                FROM data_items 
                WHERE embedding_status = 'pending'
                ORDER BY created_at ASC
                LIMIT ?
            """, (limit,))
            
            return DatabaseRowParser.parse_rows_with_metadata(
                [dict(row) for row in cursor.fetchall()]
            )
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get database-backed setting"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT value FROM system_settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            if row:
                parsed = JSONMetadataParser.parse_metadata(row['value'])
                return parsed if parsed is not None else row['value']
            return default
    
    def set_setting(self, key: str, value: Any):
        """Set database-backed setting"""
        with self.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO system_settings (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            """, (key, JSONMetadataParser.serialize_metadata(value) or value))
            conn.commit()
    
    def register_data_source(self, namespace: str, source_type: str, metadata: Dict = None):
        """Register a new data source"""
        with self.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO data_sources 
                (namespace, source_type, metadata, first_seen)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """, (namespace, source_type, JSONMetadataParser.serialize_metadata(metadata)))
            conn.commit()
    
    def get_active_namespaces(self) -> List[str]:
        """Get list of active data source namespaces"""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT namespace FROM data_sources 
                WHERE is_active = TRUE
                ORDER BY namespace
            """)
            return [row['namespace'] for row in cursor.fetchall()]
    
    def update_source_item_count(self, namespace: str):
        """Update item count for a data source"""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT COUNT(*) as count FROM data_items WHERE namespace = ?
            """, (namespace,))
            count = cursor.fetchone()['count']
            
            conn.execute("""
                UPDATE data_sources 
                SET item_count = ?
                WHERE namespace = ?
            """, (count, namespace))
            conn.commit()
            
            return count
    
    def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        with self.get_connection() as conn:
            # Total items
            cursor = conn.execute("SELECT COUNT(*) as count FROM data_items")
            total_items = cursor.fetchone()['count']
            
            # Items by namespace
            cursor = conn.execute("""
                SELECT namespace, COUNT(*) as count 
                FROM data_items 
                GROUP BY namespace
                ORDER BY count DESC
            """)
            namespace_counts = {row['namespace']: row['count'] for row in cursor.fetchall()}
            
            # Embedding status
            cursor = conn.execute("""
                SELECT embedding_status, COUNT(*) as count 
                FROM data_items 
                GROUP BY embedding_status
            """)
            embedding_status = {row['embedding_status']: row['count'] for row in cursor.fetchall()}
            
            # Data sources
            cursor = conn.execute("SELECT COUNT(*) as count FROM data_sources WHERE is_active = TRUE")
            active_sources = cursor.fetchone()['count']
            
            return {
                'total_items': total_items,
                'namespace_counts': namespace_counts,
                'embedding_status': embedding_status,
                'active_sources': active_sources,
                'database_path': self.db_path,
                'database_size_mb': os.path.getsize(self.db_path) / (1024 * 1024) if os.path.exists(self.db_path) else 0
            }
    
    def store_chat_message(self, user_message: str, assistant_response: str):
        """Store a chat message exchange"""
        with self.get_connection() as conn:
            conn.execute("""
                INSERT INTO chat_messages (user_message, assistant_response)
                VALUES (?, ?)
            """, (user_message, assistant_response))
            conn.commit()
    
    def get_chat_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent chat history"""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT id, user_message, assistant_response, timestamp
                FROM chat_messages
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,))
            
            messages = []
            for row in cursor.fetchall():
                messages.append({
                    'id': row['id'],
                    'user_message': row['user_message'],
                    'assistant_response': row['assistant_response'],
                    'timestamp': row['timestamp']
                })
            
            return list(reversed(messages))
    
    def get_days_with_data(self, namespaces: Optional[List[str]] = None) -> List[str]:
        """Get list of days that have data"""
        with self.get_connection() as conn:
            query = """
                SELECT DISTINCT days_date
                FROM data_items
                WHERE days_date IS NOT NULL
            """
            params = []
            
            if namespaces:
                placeholders = ','.join('?' * len(namespaces))
                query += f" AND namespace IN ({placeholders})"
                params.extend(namespaces)
            
            query += " ORDER BY days_date DESC"
            
            cursor = conn.execute(query, params)
            return [row['days_date'] for row in cursor.fetchall()]
    
    def get_all_namespaces(self) -> List[str]:
        """Get all distinct namespaces"""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT DISTINCT namespace
                FROM data_items
                WHERE namespace IS NOT NULL
                ORDER BY namespace
            """)
            return [row['namespace'] for row in cursor.fetchall()]
    
    async def fetch_one(self, query: str, params: tuple = None) -> Optional[Dict[str, Any]]:
        """Async wrapper for fetching one row"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute(query, params or ())
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Error in fetch_one: {e}")
            raise

    async def execute_query(self, query: str, params: tuple = None) -> None:
        """Async wrapper for executing queries"""
        try:
            with self.get_connection() as conn:
                conn.execute(query, params or ())
                conn.commit()
        except Exception as e:
            logger.error(f"Error in execute_query: {e}")
            raise


# Alias for backward compatibility
DatabaseService = UnifiedDatabaseService