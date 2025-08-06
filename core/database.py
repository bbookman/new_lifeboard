import sqlite3
import json
import os
import re
from typing import List, Dict, Optional, Any
from contextlib import contextmanager
from datetime import datetime, timezone
import pytz

from .migrations import MigrationRunner
from .json_utils import JSONMetadataParser, DatabaseRowParser
from core.logging_config import get_logger

logger = get_logger(__name__)


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
            
            query += " ORDER BY days_date DESC"
            
            logger.info(f"[CALENDAR DEBUG] Executing query: {query}")
            logger.info(f"[CALENDAR DEBUG] Query params: {params}")
            
            cursor = conn.execute(query, params)
            results = [row['days_date'] for row in cursor.fetchall()]
            
            logger.info(f"[CALENDAR DEBUG] Query returned {len(results)} results")
            logger.info(f"[CALENDAR DEBUG] First 10 results: {results[:10] if results else 'None'}")
            
            # Also check total count of data_items for debugging
            count_cursor = conn.execute("SELECT COUNT(*) as count FROM data_items")
            total_count = count_cursor.fetchone()['count']
            logger.info(f"[CALENDAR DEBUG] Total data_items in database: {total_count}")
            
            # Check how many have days_date populated
            date_cursor = conn.execute("SELECT COUNT(*) as count FROM data_items WHERE days_date IS NOT NULL")
            date_count = date_cursor.fetchone()['count']
            logger.info(f"[CALENDAR DEBUG] Data items with days_date populated: {date_count}")
            
            return results
    
    def get_markdown_by_date(self, date: str, namespaces: Optional[List[str]] = None) -> str:
        """Extract and combine markdown content from metadata for a specific date"""
        logger.info(f"[MARKDOWN DEBUG] Getting markdown for date: {date}, namespaces: {namespaces}")
        markdown_parts = []
        
        # Use unified data_items table for all namespaces
        data_items = self.get_data_items_by_date(date, namespaces)
        logger.info(f"[MARKDOWN DEBUG] Found {len(data_items)} data items for date {date}")
        
        for i, item in enumerate(data_items, 1):
            logger.info(f"[MARKDOWN DEBUG] Processing item {i+1}/{len(data_items)}: {item.get('id', 'unknown')}")
            
            if item.get('metadata'):
                metadata = item['metadata']
                markdown_content = None
                fallback_used = None
                
                if isinstance(metadata, dict):
                    # First, try to get pre-generated cleaned markdown
                    markdown_content = metadata.get('cleaned_markdown')
                    if markdown_content:
                        fallback_used = "cleaned_markdown"
                        logger.info(f"[MARKDOWN DEBUG] Item {i+1}: Using cleaned_markdown (length: {len(markdown_content)})")
                        logger.info(f"[MARKDOWN DEBUG] Item {i+1}: Cleaned markdown preview: {repr(markdown_content[:100])}")
                        # Check if it has headers
                        has_headers = bool(re.search(r'^#+\s', markdown_content, re.MULTILINE))
                        logger.info(f"[MARKDOWN DEBUG] Item {i+1}: Has headers: {has_headers}")
                    
                    # If no cleaned markdown, try original approaches for backward compatibility
                    if not markdown_content:
                        # Try to get markdown directly
                        direct_markdown = metadata.get('markdown')
                        if direct_markdown:
                            fallback_used = "metadata.markdown"
                            logger.info(f"[MARKDOWN DEBUG] Item {i+1}: Using metadata.markdown")
                            
                            # Check if we need to deduplicate with title
                            title = metadata.get('title', '')
                            if title:
                                title_header = f"# {title}"
                                # If the direct markdown doesn't start with our title, prepend it and deduplicate
                                if not direct_markdown.strip().startswith(title_header):
                                    deduplicated_content = self._remove_duplicate_headers(direct_markdown, title_header)
                                    markdown_content = f"{title_header}\n\n{deduplicated_content}"
                                else:
                                    # Just remove any duplicate instances
                                    markdown_content = self._remove_duplicate_headers(direct_markdown, title_header)
                                    # Ensure we have at least one title header at the start
                                    if not markdown_content.strip().startswith(title_header):
                                        markdown_content = f"{title_header}\n\n{markdown_content}"
                            else:
                                markdown_content = direct_markdown
                        
                        # If no direct markdown, try to get from original_lifelog
                        if not markdown_content and 'original_lifelog' in metadata:
                            original = metadata['original_lifelog']
                            if isinstance(original, dict):
                                original_markdown = original.get('markdown')
                                if original_markdown:
                                    fallback_used = "original_lifelog.markdown"
                                    logger.info(f"[MARKDOWN DEBUG] Item {i+1}: Using original_lifelog.markdown")
                                    
                                    # Check if we need to deduplicate with title
                                    title = metadata.get('title', '')
                                    if title:
                                        title_header = f"# {title}"
                                        # If the original markdown doesn't start with our title, prepend it and deduplicate
                                        if not original_markdown.strip().startswith(title_header):
                                            deduplicated_content = self._remove_duplicate_headers(original_markdown, title_header)
                                            markdown_content = f"{title_header}\n\n{deduplicated_content}"
                                        else:
                                            # Just remove any duplicate instances
                                            markdown_content = self._remove_duplicate_headers(original_markdown, title_header)
                                            # Ensure we have at least one title header at the start
                                            if not markdown_content.strip().startswith(title_header):
                                                markdown_content = f"{title_header}\n\n{markdown_content}"
                                    else:
                                        markdown_content = original_markdown
                        
                        # If still no markdown, construct from content
                        if not markdown_content:
                            fallback_used = "constructed_from_title_content"
                            title = metadata.get('title', '')
                            logger.info(f"[MARKDOWN DEBUG] Item {i+1}: Constructing from title: '{title}'")
                            
                            content = item.get('content', '')
                            
                            if title:
                                title_header = f"# {title}"
                                # Remove any duplicate headers from content before adding our own
                                deduplicated_content = self._remove_duplicate_headers(content, title_header)
                                markdown_content = f"{title_header}\n\n{deduplicated_content}"
                            else:
                                # Create a generic header even if no title
                                generic_header = f"# Entry {item.get('source_id', 'Unknown')}"
                                deduplicated_content = self._remove_duplicate_headers(content, generic_header)
                                markdown_content = f"{generic_header}\n\n{deduplicated_content}"
                            
                            logger.info(f"[MARKDOWN DEBUG] Item {i+1}: Constructed markdown preview: {repr(markdown_content[:100])}")
                            
                            # Add timestamp if available (only for fallback case)
                            if markdown_content:
                                start_time = metadata.get('start_time')
                                if start_time:
                                    try:
                                        # Parse and format timestamp
                                        dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                                        timestamp_info = f"*{dt.strftime('%I:%M %p')}*"
                                        # Insert timestamp after the header
                                        lines = markdown_content.split('\n')
                                        if lines and lines[0].startswith('#'):
                                            lines.insert(1, timestamp_info)
                                            lines.insert(2, '')  # Add blank line
                                            markdown_content = '\n'.join(lines)
                                        else:
                                            markdown_content = f"{timestamp_info}\n\n{markdown_content}"
                                        logger.info(f"[MARKDOWN DEBUG] Item {i+1}: Added timestamp to constructed content")
                                    except Exception as e:
                                        logger.warning(f"[MARKDOWN DEBUG] Item {i+1}: Failed to parse timestamp: {e}")
                
                if markdown_content:
                    logger.info(f"[MARKDOWN DEBUG] Item {i+1}: Adding content using fallback: {fallback_used}")
                    markdown_parts.append(markdown_content)
                else:
                    logger.warning(f"[MARKDOWN DEBUG] Item {i+1}: No markdown content found for item")
            else:
                logger.warning(f"[MARKDOWN DEBUG] Item {i+1}: No metadata found")
        
        # Combine all markdown with separators
        if markdown_parts:
            combined_markdown = "\n\n---\n\n".join(markdown_parts)
            logger.info(f"[MARKDOWN DEBUG] Final combined markdown length: {len(combined_markdown)}")
            logger.info(f"[MARKDOWN DEBUG] Final markdown preview: {repr(combined_markdown[:200])}")
            
            # Check for headers in final output
            has_final_headers = bool(re.search(r'^#+\s', combined_markdown, re.MULTILINE))
            logger.info(f"[MARKDOWN DEBUG] Final markdown has headers: {has_final_headers}")
            
            return combined_markdown
        else:
            fallback_content = f"# {date}\n\nNo data available for this date."
            logger.info(f"[MARKDOWN DEBUG] No content found, returning fallback: {repr(fallback_content)}")
            return fallback_content
    
    def _remove_duplicate_headers(self, content: str, target_header: str) -> str:
        """Remove duplicate instances of a header from content"""
        if not content or not target_header:
            return content
        
        lines = content.split('\n')
        filtered_lines = []
        target_header_clean = target_header.strip()
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # If we find a matching header
            if line == target_header_clean:
                # Skip this line and any immediately following empty lines
                i += 1
                while i < len(lines) and not lines[i].strip():
                    i += 1
                continue
            else:
                filtered_lines.append(lines[i])
                i += 1
        
        return '\n'.join(filtered_lines)

    
