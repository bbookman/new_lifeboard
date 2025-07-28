import sqlite3
import json
import os
import uuid
from typing import List, Dict, Optional, Any
from contextlib import contextmanager
from datetime import datetime, timezone
import pytz

from .migrations import MigrationRunner
from .json_utils import JSONMetadataParser, DatabaseRowParser


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
        """Initialize database using migration system"""
        migration_runner = MigrationRunner(self.db_path)
        result = migration_runner.run_migrations()
        
        if not result["success"]:
            raise RuntimeError(f"Database initialization failed: {result['errors']}")
    
    def store_data_item(self, id: str, namespace: str, source_id: str, 
                       content: str, metadata: Dict = None, days_date: str = None, content_hash: Optional[int] = None):
        """Store data item with namespaced ID"""
        with self.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO data_items 
                (id, namespace, source_id, content, metadata, days_date, content_hash, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (id, namespace, source_id, content, 
                  JSONMetadataParser.serialize_metadata(metadata), days_date, content_hash))
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
    
    def get_pending_embeddings(self, limit: int = 100, most_recent_first: bool = False) -> List[Dict]:
        """Get data items that need embedding"""
        order_clause = "ORDER BY created_at DESC" if most_recent_first else "ORDER BY created_at ASC"
        
        with self.get_connection() as conn:
            cursor = conn.execute(f"""
                SELECT id, namespace, source_id, content, metadata
                FROM data_items 
                WHERE embedding_status = 'pending'
                {order_clause}
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
                value = row['value']
                # Only try JSON parsing if value looks like JSON (starts with { or [)
                if value and isinstance(value, str) and value.strip().startswith(('{', '[')):
                    parsed = JSONMetadataParser.parse_metadata(value)
                    return parsed if parsed is not None else value
                # Return plain string value directly
                return value
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
    
    def store_chat_message(self, user_message: str, assistant_response: str, 
                         session_id: Optional[str] = None, 
                         context_summary: Optional[str] = None,
                         entities_mentioned: Optional[List[str]] = None,
                         topics: Optional[List[str]] = None,
                         processing_time_ms: Optional[int] = None):
        """Store a chat message exchange with enhanced conversation memory"""
        with self.get_connection() as conn:
            # Generate session ID if not provided
            if session_id is None:
                session_id = self._get_or_create_session_id(conn)
            
            # Convert lists to JSON strings
            entities_json = json.dumps(entities_mentioned) if entities_mentioned else None
            topics_json = json.dumps(topics) if topics else None
            
            conn.execute("""
                INSERT INTO chat_messages 
                (user_message, assistant_response, session_id, context_summary, 
                 entities_mentioned, topics, processing_time_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (user_message, assistant_response, session_id, context_summary,
                  entities_json, topics_json, processing_time_ms))
            
            # Update conversation session
            self._update_conversation_session(conn, session_id, entities_mentioned, topics)
            
            conn.commit()
            return session_id
    
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
    
    def extract_date_from_timestamp(self, timestamp_str: str, user_timezone: str = "UTC") -> Optional[str]:
        """Extract date string (YYYY-MM-DD) from timestamp with timezone conversion"""
        if not timestamp_str:
            return None
        
        try:
            # Parse ISO-8601 timestamp
            if timestamp_str.endswith('Z'):
                # UTC timestamp
                dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            elif '+' in timestamp_str or timestamp_str.endswith(tuple(f"-{i:02d}:00" for i in range(24))):
                # Already has timezone info
                dt = datetime.fromisoformat(timestamp_str)
            else:
                # Assume UTC if no timezone info
                dt = datetime.fromisoformat(timestamp_str).replace(tzinfo=timezone.utc)
            
            # Convert to user timezone
            if user_timezone != "UTC":
                try:
                    user_tz = pytz.timezone(user_timezone)
                    dt = dt.astimezone(user_tz)
                except Exception:
                    # Fallback to UTC if timezone conversion fails
                    pass
            
            # Return date in YYYY-MM-DD format
            return dt.strftime('%Y-%m-%d')
            
        except (ValueError, TypeError) as e:
            return None
    
    def get_data_items_by_date_range(self, start_date: str, end_date: str, 
                                   namespaces: Optional[List[str]] = None,
                                   limit: int = 100) -> List[Dict]:
        """Get data items within a date range"""
        with self.get_connection() as conn:
            # Base query
            query = """
                SELECT id, namespace, source_id, content, metadata, days_date, created_at, updated_at
                FROM data_items 
                WHERE days_date >= ? AND days_date <= ?
            """
            params = [start_date, end_date]
            
            # Add namespace filter if provided
            if namespaces:
                placeholders = ','.join('?' * len(namespaces))
                query += f" AND namespace IN ({placeholders})"
                params.extend(namespaces)
            
            # Add ordering and limit
            query += " ORDER BY days_date DESC, updated_at DESC LIMIT ?"
            params.append(limit)
            
            cursor = conn.execute(query, params)
            
            return DatabaseRowParser.parse_rows_with_metadata(
                [dict(row) for row in cursor.fetchall()]
            )
    
    def get_data_items_by_date(self, date: str, namespaces: Optional[List[str]] = None) -> List[Dict]:
        """Get all data items for a specific date"""
        return self.get_data_items_by_date_range(date, date, namespaces, limit=1000)
    
    def get_available_dates(self, namespaces: Optional[List[str]] = None) -> List[str]:
        """Get list of dates that have data available"""
        with self.get_connection() as conn:
            query = """
                SELECT DISTINCT days_date 
                FROM data_items 
                WHERE days_date IS NOT NULL
            """
            params = []
            
            # Add namespace filter if provided
            if namespaces:
                placeholders = ','.join('?' * len(namespaces))
                query += f" AND namespace IN ({placeholders})"
                params.extend(namespaces)
            
            query += " ORDER BY days_date DESC"
            
            cursor = conn.execute(query, params)
            return [row['days_date'] for row in cursor.fetchall()]
    
    def get_migration_status(self) -> Dict[str, Any]:
        """Get database migration status"""
        migration_runner = MigrationRunner(self.db_path)
        return migration_runner.get_migration_status()
    
    def _get_or_create_session_id(self, conn: sqlite3.Connection) -> str:
        """Get or create a conversation session ID"""
        # Check for recent session (within last hour)
        cursor = conn.execute("""
            SELECT session_id FROM conversation_sessions 
            WHERE last_activity > datetime('now', '-1 hour')
            ORDER BY last_activity DESC 
            LIMIT 1
        """)
        
        row = cursor.fetchone()
        if row:
            session_id = row['session_id']
            # Update last activity
            conn.execute("""
                UPDATE conversation_sessions 
                SET last_activity = CURRENT_TIMESTAMP 
                WHERE session_id = ?
            """, (session_id,))
            return session_id
        else:
            # Create new session
            session_id = str(uuid.uuid4())
            conn.execute("""
                INSERT INTO conversation_sessions (session_id, message_count)
                VALUES (?, 0)
            """, (session_id,))
            return session_id
    
    def _update_conversation_session(self, conn: sqlite3.Connection, 
                                   session_id: str, 
                                   entities: Optional[List[str]] = None,
                                   topics: Optional[List[str]] = None):
        """Update conversation session with new entities and topics"""
        # Get current session data
        cursor = conn.execute("""
            SELECT entities_discussed, topics_discussed, message_count
            FROM conversation_sessions 
            WHERE session_id = ?
        """, (session_id,))
        
        row = cursor.fetchone()
        if not row:
            return
        
        # Parse existing entities and topics
        existing_entities = []
        if row['entities_discussed']:
            try:
                existing_entities = json.loads(row['entities_discussed'])
            except json.JSONDecodeError:
                pass
        
        existing_topics = []
        if row['topics_discussed']:
            try:
                existing_topics = json.loads(row['topics_discussed'])
            except json.JSONDecodeError:
                pass
        
        # Merge new entities and topics
        if entities:
            existing_entities = list(set(existing_entities + entities))
        
        if topics:
            existing_topics = list(set(existing_topics + topics))
        
        # Update session
        conn.execute("""
            UPDATE conversation_sessions 
            SET last_activity = CURRENT_TIMESTAMP,
                message_count = message_count + 1,
                entities_discussed = ?,
                topics_discussed = ?
            WHERE session_id = ?
        """, (json.dumps(existing_entities), json.dumps(existing_topics), session_id))
    
    def get_conversation_context(self, session_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get conversation context for a session"""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT id, user_message, assistant_response, timestamp, 
                       context_summary, entities_mentioned, topics
                FROM chat_messages
                WHERE session_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (session_id, limit))
            
            messages = []
            for row in cursor.fetchall():
                # Parse JSON fields
                entities = None
                if row['entities_mentioned']:
                    try:
                        entities = json.loads(row['entities_mentioned'])
                    except json.JSONDecodeError:
                        pass
                
                topics = None
                if row['topics']:
                    try:
                        topics = json.loads(row['topics'])
                    except json.JSONDecodeError:
                        pass
                
                messages.append({
                    'id': row['id'],
                    'user_message': row['user_message'],
                    'assistant_response': row['assistant_response'],
                    'timestamp': row['timestamp'],
                    'context_summary': row['context_summary'],
                    'entities_mentioned': entities,
                    'topics': topics
                })
            
            # Return in chronological order (oldest first)
            return list(reversed(messages))
    
    def get_session_summary(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get summary of a conversation session"""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT session_id, started_at, last_activity, message_count,
                       session_summary, entities_discussed, topics_discussed
                FROM conversation_sessions
                WHERE session_id = ?
            """, (session_id,))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            # Parse JSON fields
            entities = []
            if row['entities_discussed']:
                try:
                    entities = json.loads(row['entities_discussed'])
                except json.JSONDecodeError:
                    pass
            
            topics = []
            if row['topics_discussed']:
                try:
                    topics = json.loads(row['topics_discussed'])
                except json.JSONDecodeError:
                    pass
            
            return {
                'session_id': row['session_id'],
                'started_at': row['started_at'],
                'last_activity': row['last_activity'],
                'message_count': row['message_count'],
                'session_summary': row['session_summary'],
                'entities_discussed': entities,
                'topics_discussed': topics
            }