import sqlite3
import json
import os
import logging
from typing import List, Dict, Optional, Any
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class DatabaseService:
    def __init__(self, db_path: str = "lifeboard.db"):
        self.db_path = db_path
        self._init_database()
    
    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def _init_database(self):
        """Initialize database with required tables"""
        with self.get_connection() as conn:
            # System settings table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS system_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Data sources registry
            conn.execute("""
                CREATE TABLE IF NOT EXISTS data_sources (
                    namespace TEXT PRIMARY KEY,
                    source_type TEXT NOT NULL,
                    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    item_count INTEGER DEFAULT 0,
                    metadata TEXT,
                    is_active BOOLEAN DEFAULT TRUE
                )
            """)
            
            # Enhanced data storage with preprocessing fields
            conn.execute("""
                CREATE TABLE IF NOT EXISTS data_items (
                    id TEXT PRIMARY KEY,
                    namespace TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata TEXT,
                    
                    -- Structured preprocessing outputs
                    summary_content TEXT,
                    named_entities TEXT,
                    content_classification TEXT,
                    temporal_context TEXT,
                    conversation_turns TEXT,
                    
                    -- Quality metrics
                    content_quality_score REAL,
                    semantic_density REAL,
                    
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    embedding_status TEXT DEFAULT 'pending',
                    preprocessing_status TEXT DEFAULT 'pending',
                    FOREIGN KEY (namespace) REFERENCES data_sources(namespace)
                )
            """)
            
            # Chat messages table for Phase 7
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_message TEXT NOT NULL,
                    assistant_response TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes
            conn.execute("CREATE INDEX IF NOT EXISTS idx_data_items_namespace ON data_items(namespace)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_data_items_embedding_status ON data_items(embedding_status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_data_items_updated_at ON data_items(updated_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_messages_timestamp ON chat_messages(timestamp)")
            
            conn.commit()
    
    def store_data_item(self, id: str, namespace: str, source_id: str, 
                       content: str, metadata: Dict = None):
        """Store data item with namespaced ID and extract preprocessed data"""
        if metadata is None:
            metadata = {}
        
        # Extract preprocessed data from metadata for dedicated columns
        summary_content = None
        named_entities = None
        content_classification = None
        temporal_context = None
        conversation_turns = None
        content_quality_score = None
        semantic_density = None
        preprocessing_status = 'pending'
        
        if metadata:
            # Extract summary content - use the cleaned content which is stored in the content field after processing
            processing_history = metadata.get('processing_history', [])
            has_advanced_cleaning = any(p.get('processor') == 'AdvancedCleaningProcessor' for p in processing_history)
            
            if has_advanced_cleaning and content:
                # The content has already been cleaned by AdvancedCleaningProcessor
                summary_content = content[:2000]  # Limit length
            
            # Extract named entities
            named_entities_data = metadata.get('named_entities', {})
            if named_entities_data:
                named_entities = json.dumps(named_entities_data)
            
            # Extract content classification
            content_classification_data = metadata.get('content_classification', {})
            if content_classification_data:
                content_classification = json.dumps(content_classification_data)
            
            # Extract temporal context
            temporal_context_data = metadata.get('temporal_context', {})
            if temporal_context_data:
                temporal_context = json.dumps(temporal_context_data)
            
            # Extract conversation turns from segmentation
            segmentation_data = metadata.get('segmentation', {})
            if segmentation_data:
                conversation_turns = json.dumps(segmentation_data)
            
            # Calculate content quality score based on available processing
            processing_history = metadata.get('processing_history', [])
            if processing_history:
                # Score based on number of successful processing steps
                max_processors = 7  # Advanced cleaning, entities, classification, temporal, etc.
                actual_processors = len(processing_history)
                content_quality_score = min(1.0, actual_processors / max_processors)
                preprocessing_status = 'completed'
            
            # Calculate semantic density based on content stats
            content_stats = metadata.get('content_stats', {})
            if content_stats:
                word_count = content_stats.get('word_count', 0)
                char_count = content_stats.get('character_count', 0)
                if word_count > 0 and char_count > 0:
                    # Simple metric: average word length and paragraph density
                    avg_word_length = char_count / word_count
                    paragraph_count = content_stats.get('paragraph_count', 1)
                    semantic_density = min(1.0, (avg_word_length * paragraph_count) / 100)
        
        with self.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO data_items 
                (id, namespace, source_id, content, metadata, 
                 summary_content, named_entities, content_classification, 
                 temporal_context, conversation_turns, content_quality_score, 
                 semantic_density, preprocessing_status, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (id, namespace, source_id, content, 
                  json.dumps(metadata),
                  summary_content, named_entities, content_classification,
                  temporal_context, conversation_turns, content_quality_score,
                  semantic_density, preprocessing_status))
            conn.commit()
    
    def get_data_items_by_ids(self, ids: List[str]) -> List[Dict]:
        """Batch fetch data items by namespaced IDs"""
        logger.debug(f"Database Debug - Fetching data items for {len(ids) if ids else 0} IDs")
        if not ids:
            logger.debug("Database Debug - No IDs provided, returning empty list")
            return []
        
        logger.debug(f"Database Debug - IDs to fetch: {ids[:5]}{'...' if len(ids) > 5 else ''}")
        placeholders = ','.join('?' * len(ids))
        with self.get_connection() as conn:
            cursor = conn.execute(f"""
                SELECT id, namespace, source_id, content, metadata, created_at, updated_at
                FROM data_items 
                WHERE id IN ({placeholders})
                ORDER BY updated_at DESC
            """, ids)
            
            results = []
            for row in cursor.fetchall():
                item = dict(row)
                # Parse JSON metadata if present
                if item['metadata']:
                    try:
                        item['metadata'] = json.loads(item['metadata'])
                    except json.JSONDecodeError:
                        logger.warning(f"Database Debug - Failed to parse metadata for item {item['id']}")
                        item['metadata'] = None
                results.append(item)
            
            logger.info(f"Database Debug - Retrieved {len(results)} data items from database")
            
            # Log sample content for debugging
            for i, item in enumerate(results[:2]):
                content_preview = item.get('content', '')[:100] + '...' if len(item.get('content', '')) > 100 else item.get('content', '')
                logger.debug(f"Database Debug - Item {i+1}: ID={item.get('id')}, namespace={item.get('namespace')}, content_preview='{content_preview}'")
            
            return results
    
    def get_data_items_by_namespace(self, namespace: str, limit: int = 100) -> List[Dict]:
        """Get data items for a specific namespace"""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT id, namespace, source_id, content, metadata, created_at, updated_at
                FROM data_items 
                WHERE namespace = ?
                ORDER BY updated_at DESC
                LIMIT ?
            """, (namespace, limit))
            
            results = []
            for row in cursor.fetchall():
                item = dict(row)
                if item['metadata']:
                    try:
                        item['metadata'] = json.loads(item['metadata'])
                    except json.JSONDecodeError:
                        item['metadata'] = None
                results.append(item)
            
            return results
    
    def update_embedding_status(self, id: str, status: str):
        """Update embedding status for a data item"""
        with self.get_connection() as conn:
            conn.execute("""
                UPDATE data_items 
                SET embedding_status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (status, id))
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
            
            results = []
            for row in cursor.fetchall():
                item = dict(row)
                if item['metadata']:
                    try:
                        item['metadata'] = json.loads(item['metadata'])
                    except json.JSONDecodeError:
                        item['metadata'] = None
                results.append(item)
            
            return results
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get database-backed setting"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT value FROM system_settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            if row:
                try:
                    return json.loads(row['value'])
                except json.JSONDecodeError:
                    return row['value']
            return default
    
    def set_setting(self, key: str, value: Any):
        """Set database-backed setting"""
        with self.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO system_settings (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            """, (key, json.dumps(value) if not isinstance(value, str) else value))
            conn.commit()
    
    def register_data_source(self, namespace: str, source_type: str, metadata: Dict = None):
        """Register a new data source"""
        with self.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO data_sources 
                (namespace, source_type, metadata, first_seen)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """, (namespace, source_type, json.dumps(metadata) if metadata else None))
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
            
            # Return in chronological order (oldest first)
            return list(reversed(messages))