import sqlite3
import json
import os
import logging
from typing import List, Dict, Optional, Any
from contextlib import contextmanager
from datetime import datetime, timezone
import pytz

from .migrations import MigrationRunner
from .json_utils import JSONMetadataParser, DatabaseRowParser

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
        """Initialize database using migration system"""
        migration_runner = MigrationRunner(self.db_path)
        result = migration_runner.run_migrations()
        
        if not result["success"]:
            raise RuntimeError(f"Database initialization failed: {result['errors']}")
    
    def store_data_item(self, id: str, namespace: str, source_id: str, 
                       content: str, metadata: Dict = None, days_date: str = None):
        """Store data item with namespaced ID"""
        with self.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO data_items 
                (id, namespace, source_id, content, metadata, days_date, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (id, namespace, source_id, content, 
                  JSONMetadataParser.serialize_metadata(metadata), days_date))
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
                # Try to parse as JSON, fallback to string value
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
            elif '+' in timestamp_str or '-' in timestamp_str[10:]:
                # Already has timezone info
                dt = datetime.fromisoformat(timestamp_str)
            else:
                # Assume UTC if no timezone info
                dt = datetime.fromisoformat(timestamp_str).replace(tzinfo=timezone.utc)

            # Always convert to the target timezone
            try:
                target_tz = pytz.timezone(user_timezone)
                dt = dt.astimezone(target_tz)
            except Exception:
                # If target timezone is invalid, convert to UTC as a fallback
                dt = dt.astimezone(pytz.utc)

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
    
    def get_days_with_data(self, namespaces: Optional[List[str]] = None) -> List[str]:
        """Get list of days that have data (for calendar indicators)"""
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
            
            cursor = conn.execute(query, params)
            return sorted([row['days_date'] for row in cursor.fetchall()])
    
    def get_markdown_by_date(self, date: str, namespaces: Optional[List[str]] = None) -> str:
        """Extract and combine markdown content from metadata for a specific date"""
        markdown_parts = []
        
        # Handle limitless namespace specially - use dedicated limitless table
        if namespaces and namespaces == ['limitless']:
            limitless_items = self.get_limitless_items_by_date(date)
            
            for item in limitless_items:
                try:
                    # Parse raw_data to get original lifelog
                    raw_lifelog = json.loads(item['raw_data'])
                    
                    # Extract markdown content
                    markdown_content = None
                    
                    # First, try to get markdown directly from original lifelog
                    if raw_lifelog.get('markdown'):
                        markdown_content = raw_lifelog['markdown']
                    else:
                        # Construct from processed content with title
                        if item.get('title'):
                            markdown_content = f"# {item['title']}\n\n{item['processed_content']}"
                        else:
                            markdown_content = item['processed_content']
                    
                    # Add timestamp if available
                    if markdown_content and item.get('start_time'):
                        timestamp_info = ""
                        try:
                            # Parse and format timestamp
                            dt = datetime.fromisoformat(item['start_time'].replace('Z', '+00:00'))
                            timestamp_info = f"*{dt.strftime('%I:%M %p')}*\n\n"
                        except:
                            pass
                        
                        markdown_parts.append(f"{timestamp_info}{markdown_content}")
                    elif markdown_content:
                        markdown_parts.append(markdown_content)
                        
                except Exception as e:
                    logger.warning(f"Failed to process limitless item for markdown: {e}")
                    continue
        else:
            # Use regular data_items table for other namespaces
            data_items = self.get_data_items_by_date(date, namespaces)
            
            for item in data_items:
                if item.get('metadata'):
                    metadata = item['metadata']
                    
                    # Extract markdown from different possible locations in metadata
                    markdown_content = None
                    
                    # First, try to get markdown directly
                    if isinstance(metadata, dict):
                        markdown_content = metadata.get('markdown')
                        
                        # If no direct markdown, try to get from original_lifelog
                        if not markdown_content and 'original_lifelog' in metadata:
                            original = metadata['original_lifelog']
                            if isinstance(original, dict):
                                markdown_content = original.get('markdown')
                        
                        # If still no markdown, construct from content
                        if not markdown_content:
                            title = metadata.get('title', '')
                            if title:
                                markdown_content = f"# {title}\n\n{item.get('content', '')}"
                            else:
                                markdown_content = item.get('content', '')
                    
                    # Add timestamp if available
                    if markdown_content:
                        timestamp_info = ""
                        if isinstance(metadata, dict):
                            start_time = metadata.get('start_time')
                            if start_time:
                                try:
                                    # Parse and format timestamp
                                    dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                                    timestamp_info = f"*{dt.strftime('%I:%M %p')}*\n\n"
                                except:
                                    pass
                        
                        markdown_parts.append(f"{timestamp_info}{markdown_content}")
        
        # Combine all markdown with separators
        if markdown_parts:
            return "\n\n---\n\n".join(markdown_parts)
        else:
            return f"# {date}\n\nNo data available for this date."

    
    def store_limitless_item(self, lifelog_id: str, title: str, start_time: str, 
                           end_time: str, is_starred: bool, updated_at_api: str,
                           processed_content: str, raw_data: str, days_date: str) -> str:
        """Store Limitless lifelog data and return the generated ID"""
        item_id = f"limitless:{lifelog_id}"
        
        with self.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO limitless 
                (id, lifelog_id, title, start_time, end_time, is_starred, 
                 updated_at_api, processed_content, raw_data, days_date, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (item_id, lifelog_id, title, start_time, end_time, is_starred,
                  updated_at_api, processed_content, raw_data, days_date))
            conn.commit()
        
        return item_id
    
    def get_limitless_items(self, limit: int = 100) -> List[Dict]:
        """Get Limitless lifelog items"""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT id, lifelog_id, title, start_time, end_time, is_starred,
                       updated_at_api, processed_content, raw_data, days_date,
                       created_at, updated_at
                FROM limitless
                ORDER BY start_time DESC
                LIMIT ?
            """, (limit,))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_limitless_item_by_lifelog_id(self, lifelog_id: str) -> Optional[Dict]:
        """Get specific Limitless item by lifelog ID"""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT id, lifelog_id, title, start_time, end_time, is_starred,
                       updated_at_api, processed_content, raw_data, days_date,
                       created_at, updated_at
                FROM limitless
                WHERE lifelog_id = ?
            """, (lifelog_id,))
            
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_limitless_items_by_date(self, date: str) -> List[Dict]:
        """Get Limitless items for a specific date"""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT id, lifelog_id, title, start_time, end_time, is_starred,
                       updated_at_api, processed_content, raw_data, days_date,
                       created_at, updated_at
                FROM limitless
                WHERE days_date = ?
                ORDER BY start_time ASC
            """, (date,))
            
            return [dict(row) for row in cursor.fetchall()]
    
