import sqlite3
import aiosqlite
import json
import os
import logging
import re
import time
from typing import List, Dict, Optional, Any
from contextlib import contextmanager, asynccontextmanager
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
    
    @asynccontextmanager
    async def get_async_connection(self):
        """Async context manager for database connections"""
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            try:
                yield conn
            finally:
                # Connection automatically closed by aiosqlite context manager
                pass
    
    @asynccontextmanager
    async def async_transaction(self):
        """Async transaction context manager with rollback support"""
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            try:
                await conn.execute("BEGIN")
                yield conn
                await conn.commit()
            except Exception:
                await conn.rollback()
                raise
    
    def _init_database(self):
        """Initialize database using migration system"""
        migration_runner = MigrationRunner(self.db_path)
        result = migration_runner.run_migrations()
        
        if not result["success"]:
            raise RuntimeError(f"Database initialization failed: {result['errors']}")
    
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
    
    def _extract_start_time_for_sorting(self, item_dict: Dict) -> Optional[datetime]:
        """
        Extract start_time from item metadata for chronological sorting.
        Returns datetime object if found, None otherwise.
        """
        try:
            metadata = item_dict.get('metadata', {})
            if not metadata:
                return None
            
            # Parse metadata if it's a JSON string
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except (json.JSONDecodeError, TypeError):
                    return None
            
            if not isinstance(metadata, dict):
                return None
            
            # Try different possible locations for start_time
            start_time = None
            
            # Check processed_response first (new metadata structure)
            if 'processed_response' in metadata:
                start_time = metadata['processed_response'].get('start_time')
            
            # Check original_response (new metadata structure)
            if not start_time and 'original_response' in metadata:
                start_time = metadata['original_response'].get('startTime')
            
            # Check original_lifelog (legacy structure)
            if not start_time and 'original_lifelog' in metadata:
                original = metadata['original_lifelog']
                if isinstance(original, dict):
                    start_time = original.get('startTime')
            
            # Check top-level metadata (legacy)
            if not start_time:
                start_time = metadata.get('start_time') or metadata.get('startTime')
            
            if start_time:
                # Parse the timestamp
                if start_time.endswith('Z'):
                    dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                elif '+' in start_time or start_time.endswith('UTC'):
                    dt = datetime.fromisoformat(start_time.replace('UTC', '+00:00'))
                else:
                    dt = datetime.fromisoformat(start_time)
                
                return dt
            
        except (ValueError, TypeError, AttributeError) as e:
            logger.debug(f"Could not extract start_time for sorting: {e}")
            
        return None
    
    def _sort_items_chronologically(self, items: List[Dict]) -> List[Dict]:
        """
        Sort items chronologically within each day, maintaining database ordering as fallback.
        """
        def sort_key(item):
            # Extract start_time for sorting
            start_time = self._extract_start_time_for_sorting(item)
            
            if start_time:
                # Use actual start_time for chronological ordering (ascending within day)
                return (item.get('days_date', ''), start_time, item.get('updated_at', ''))
            else:
                # Fallback to existing ordering for items without start_time
                return (item.get('days_date', ''), datetime.min, item.get('updated_at', ''))
        
        return sorted(items, key=sort_key)
    
    def get_data_items_by_date_range(self, start_date: str, end_date: str, 
                                   namespaces: Optional[List[str]] = None,
                                   limit: int = 100) -> List[Dict]:
        """Get data items within a date range, sorted chronologically within each day"""
        with self.get_connection() as conn:
            # Base query - fetch more items initially to allow for proper sorting
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
            
            # Initial ordering by days_date and updated_at for database efficiency
            # We'll do chronological sorting in Python after fetching
            query += " ORDER BY days_date DESC, updated_at DESC"
            
            cursor = conn.execute(query, params)
            raw_items = [dict(row) for row in cursor.fetchall()]
            
            # Parse metadata
            parsed_items = DatabaseRowParser.parse_rows_with_metadata(raw_items)
            
            # Apply chronological sorting (this will sort by start_time within each day)
            sorted_items = self._sort_items_chronologically(parsed_items)
            
            # Apply limit after sorting to ensure we get the right items
            return sorted_items[:limit] if limit else sorted_items
    
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
    
    def get_all_namespaces(self) -> List[str]:
        """Get a list of all distinct namespaces present in the data_items table."""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT DISTINCT namespace
                FROM data_items
                WHERE namespace IS NOT NULL
                ORDER BY namespace
            """)
            return [row['namespace'] for row in cursor.fetchall()]

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
                    # PRIORITY 1: Check for speaker-labeled content (processed by speaker labeling service)
                    if 'speaker_labeled_content' in metadata:
                        markdown_content = metadata['speaker_labeled_content']
                        fallback_used = "speaker_labeled_content"
                        logger.info(f"[MARKDOWN DEBUG] Item {i+1}: Using speaker-labeled content (length: {len(markdown_content)})")
                        logger.info(f"[MARKDOWN DEBUG] Item {i+1}: Speaker-labeled preview: {repr(markdown_content[:100])}")

                if isinstance(metadata, dict) and not markdown_content:
                    # Try to get pre-generated cleaned markdown
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

    async def fetch_one(self, query: str, params: tuple = None) -> Optional[Dict[str, Any]]:
        """
        Real async method for fetching one row from database.
        Converted from fake async to real async using aiosqlite.
        """
        try:
            async with self.get_async_connection() as conn:
                async with conn.execute(query, params or ()) as cursor:
                    row = await cursor.fetchone()
                    return dict(row) if row else None
        except Exception as e:
            logger.error(f"Error in fetch_one: {e}")
            raise

    async def execute_query(self, query: str, params: tuple = None) -> None:
        """
        Real async method for executing a query (INSERT, UPDATE, DELETE).
        Converted from fake async to real async using aiosqlite.
        """
        try:
            async with self.get_async_connection() as conn:
                await conn.execute(query, params or ())
                await conn.commit()
        except Exception as e:
            logger.error(f"Error in execute_query: {e}")
            raise

    # Async versions of core CRUD operations
    
    async def async_store_data_item(self, id: str, namespace: str, source_id: str, 
                                  content: str, metadata: Dict = None, days_date: str = None,
                                  ingestion_status: str = 'complete'):
        """Async version of store_data_item"""
        start_time = time.time()
        
        # Twitter-specific logging
        if namespace == 'twitter':
            logger.info(f"[TWITTER TRACE] Database storage starting for Twitter item: source_id={source_id}")
            logger.info(f"[TWITTER TRACE] Twitter data details: content_length={len(content) if content else 0}, "
                       f"metadata_keys={list(metadata.keys()) if metadata else []}, days_date={days_date}")
            logger.info(f"[TWITTER TRACE] Twitter storage SQL: INSERT OR REPLACE INTO data_items with id={id}")
        
        try:
            serialized_metadata = JSONMetadataParser.serialize_metadata(metadata)
            
            if namespace == 'twitter':
                logger.info(f"[TWITTER TRACE] Twitter metadata serialization: "
                           f"original_size={len(str(metadata)) if metadata else 0}, "
                           f"serialized_size={len(serialized_metadata) if serialized_metadata else 0}")
            
            async with self.get_async_connection() as conn:
                await conn.execute("""
                    INSERT OR REPLACE INTO data_items 
                    (id, namespace, source_id, content, metadata, days_date, updated_at, ingestion_status)
                    VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
                """, (id, namespace, source_id, content, 
                      serialized_metadata, days_date, ingestion_status))
                await conn.commit()
                
                execution_time = (time.time() - start_time) * 1000
                
                if namespace == 'twitter':
                    logger.info(f"[TWITTER TRACE] Twitter data storage completed successfully in {execution_time:.2f}ms")
                    logger.info(f"[TWITTER TRACE] Twitter item stored: id={id}, source_id={source_id}, status={ingestion_status}")
                    
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            if namespace == 'twitter':
                logger.error(f"[TWITTER TRACE] Twitter data storage failed after {execution_time:.2f}ms: {e}")
                logger.error(f"[TWITTER TRACE] Twitter storage error context: id={id}, source_id={source_id}, "
                            f"content_length={len(content) if content else 0}")
            logger.error(f"Error in async_store_data_item: {e}")
            raise
    
    async def async_get_data_items_by_ids(self, ids: List[str]) -> List[Dict]:
        """Async version of get_data_items_by_ids"""
        if not ids:
            return []
        
        try:
            placeholders = ','.join('?' * len(ids))
            async with self.get_async_connection() as conn:
                async with conn.execute(f"""
                    SELECT id, namespace, source_id, content, metadata, days_date, created_at, updated_at, embedding_status, ingestion_status
                    FROM data_items 
                    WHERE id IN ({placeholders})
                    ORDER BY updated_at DESC
                """, ids) as cursor:
                    rows = await cursor.fetchall()
                    
                    return DatabaseRowParser.parse_rows_with_metadata(
                        [dict(row) for row in rows]
                    )
        except Exception as e:
            logger.error(f"Error in async_get_data_items_by_ids: {e}")
            raise

    async def async_get_data_items_by_namespace(self, namespace: str, limit: int = 100) -> List[Dict]:
        """Async version of get_data_items_by_namespace"""
        start_time = time.time()
        
        
        try:
            async with self.get_async_connection() as conn:
                async with conn.execute("""
                    SELECT id, namespace, source_id, content, metadata, days_date, created_at, updated_at
                    FROM data_items 
                    WHERE namespace = ?
                    ORDER BY updated_at DESC
                    LIMIT ?
                """, (namespace, limit)) as cursor:
                    rows = await cursor.fetchall()
                    
                    execution_time = (time.time() - start_time) * 1000
                    
                    
                    parsed_rows = DatabaseRowParser.parse_rows_with_metadata(
                        [dict(row) for row in rows]
                    )
                    
                    
                    return parsed_rows
                    
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            logger.error(f"Error in async_get_data_items_by_namespace: {e}")
            raise
    
    async def async_get_data_items_by_date_range(self, start_date: str, end_date: str, 
                                               namespaces: Optional[List[str]] = None,
                                               limit: int = 100) -> List[Dict]:
        """Async version of get_data_items_by_date_range, sorted chronologically within each day"""
        start_time = time.time()
        
        # Twitter-specific logging
        is_twitter_query = namespaces and 'twitter' in namespaces
        if is_twitter_query:
            logger.info(f"[TWITTER TRACE] Database date range query starting for Twitter: "
                       f"start_date={start_date}, end_date={end_date}, limit={limit}")
        
        try:
            # Base query - fetch more items initially to allow for proper sorting
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
            
            # Initial ordering by days_date and updated_at for database efficiency
            # We'll do chronological sorting in Python after fetching
            query += " ORDER BY days_date DESC, updated_at DESC"
            
            if is_twitter_query:
                logger.info(f"[TWITTER TRACE] Twitter date query SQL: {query}")
                logger.info(f"[TWITTER TRACE] Twitter date query params: {params}")
            
            async with self.get_async_connection() as conn:
                async with conn.execute(query, params) as cursor:
                    rows = await cursor.fetchall()
                    
                    execution_time = (time.time() - start_time) * 1000
                    
                    if is_twitter_query:
                        twitter_rows = [row for row in rows if dict(row).get('namespace') == 'twitter']
                        logger.info(f"[TWITTER TRACE] Twitter date query executed in {execution_time:.2f}ms")
                        logger.info(f"[TWITTER TRACE] Twitter date filtering results: total_rows={len(rows)}, "
                                   f"twitter_rows={len(twitter_rows)}")
                        
                        if twitter_rows:
                            sample_twitter = dict(twitter_rows[0])
                            logger.info(f"[TWITTER TRACE] Twitter sample from date range: "
                                       f"id={sample_twitter.get('id')}, days_date={sample_twitter.get('days_date')}")
                    
                    # Parse metadata
                    parsed_rows = DatabaseRowParser.parse_rows_with_metadata(
                        [dict(row) for row in rows]
                    )
                    
                    # Apply chronological sorting (this will sort by start_time within each day)
                    sorted_items = self._sort_items_chronologically(parsed_rows)
                    
                    # Apply limit after sorting to ensure we get the right items
                    final_items = sorted_items[:limit] if limit else sorted_items
                    
                    if is_twitter_query:
                        twitter_parsed = [item for item in final_items if item.get('namespace') == 'twitter']
                        logger.info(f"[TWITTER TRACE] Twitter date range parsing completed: {len(twitter_parsed)} Twitter items")
                    
                    return final_items
                    
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            if is_twitter_query:
                logger.error(f"[TWITTER TRACE] Twitter date range query failed after {execution_time:.2f}ms: {e}")
                logger.error(f"[TWITTER TRACE] Twitter date query error context: start_date={start_date}, "
                            f"end_date={end_date}, namespaces={namespaces}")
            logger.error(f"Error in async_get_data_items_by_date_range: {e}")
            raise
    
    async def async_get_data_items_by_date(self, date: str, namespaces: Optional[List[str]] = None) -> List[Dict]:
        """Async version of get_data_items_by_date"""
        # Twitter-specific logging
        is_twitter_query = namespaces and 'twitter' in namespaces
        if is_twitter_query:
            logger.info(f"[TWITTER TRACE] Database single date query starting for Twitter: date={date}")
        
        result = await self.async_get_data_items_by_date_range(date, date, namespaces, limit=1000)
        
        if is_twitter_query:
            twitter_items = [item for item in result if item.get('namespace') == 'twitter']
            logger.info(f"[TWITTER TRACE] Twitter single date query completed: {len(twitter_items)} Twitter items for {date}")
        
        return result
    
    async def async_get_available_dates(self, namespaces: Optional[List[str]] = None) -> List[str]:
        """Async version of get_available_dates"""
        try:
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
            
            async with self.get_async_connection() as conn:
                async with conn.execute(query, params) as cursor:
                    rows = await cursor.fetchall()
                    return [row['days_date'] for row in rows]
        except Exception as e:
            logger.error(f"Error in async_get_available_dates: {e}")
            raise
    
    async def async_get_days_with_data(self, namespaces: Optional[List[str]] = None) -> List[str]:
        """Async version of get_days_with_data"""
        start_time = time.time()
        
        # Twitter-specific logging
        is_twitter_query = namespaces and 'twitter' in namespaces
        if is_twitter_query:
            logger.info(f"[TWITTER TRACE] Database days with data query starting for Twitter")
        
        try:
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
            
            if is_twitter_query:
                logger.info(f"[TWITTER TRACE] Twitter days query SQL: {query}")
                logger.info(f"[TWITTER TRACE] Twitter days query params: {params}")
            
            async with self.get_async_connection() as conn:
                async with conn.execute(query, params) as cursor:
                    rows = await cursor.fetchall()
                    dates = [row['days_date'] for row in rows]
                    
                    execution_time = (time.time() - start_time) * 1000
                    
                    if is_twitter_query:
                        logger.info(f"[TWITTER TRACE] Twitter days query executed in {execution_time:.2f}ms")
                        logger.info(f"[TWITTER TRACE] Twitter data integrity check: found {len(dates)} days with Twitter data")
                        if dates:
                            logger.info(f"[TWITTER TRACE] Twitter date range: {dates[-1]} to {dates[0]} ({len(dates)} days)")
                        else:
                            logger.warning(f"[TWITTER TRACE] No Twitter data found in database - potential data integrity issue")
                    
                    return dates
                    
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            if is_twitter_query:
                logger.error(f"[TWITTER TRACE] Twitter days query failed after {execution_time:.2f}ms: {e}")
                logger.error(f"[TWITTER TRACE] Twitter days query error context: namespaces={namespaces}")
            logger.error(f"Error in async_get_days_with_data: {e}")
            raise
    
    async def async_get_all_namespaces(self) -> List[str]:
        """Async version of get_all_namespaces"""
        try:
            async with self.get_async_connection() as conn:
                async with conn.execute("""
                    SELECT DISTINCT namespace 
                    FROM data_items 
                    ORDER BY namespace
                """) as cursor:
                    rows = await cursor.fetchall()
                    return [row['namespace'] for row in rows]
        except Exception as e:
            logger.error(f"Error in async_get_all_namespaces: {e}")
            raise

    # Async versions of settings and metadata operations
    
    async def async_get_setting(self, key: str, default: Any = None) -> Any:
        """Async version of get_setting"""
        try:
            async with self.get_async_connection() as conn:
                async with conn.execute(
                    "SELECT value FROM system_settings WHERE key = ?", (key,)) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        # Try to parse as JSON, fallback to string value
                        parsed = JSONMetadataParser.parse_metadata(row['value'])
                        return parsed if parsed is not None else row['value']
                    return default
        except Exception as e:
            logger.error(f"Error in async_get_setting: {e}")
            raise
    
    async def async_set_setting(self, key: str, value: Any):
        """Async version of set_setting"""
        try:
            async with self.get_async_connection() as conn:
                await conn.execute("""
                    INSERT OR REPLACE INTO system_settings (key, value, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                """, (key, JSONMetadataParser.serialize_metadata(value) or value))
                await conn.commit()
        except Exception as e:
            logger.error(f"Error in async_set_setting: {e}")
            raise
    
    async def async_register_data_source(self, namespace: str, source_type: str, metadata: Dict = None):
        """Async version of register_data_source"""
        try:
            async with self.get_async_connection() as conn:
                await conn.execute("""
                    INSERT OR REPLACE INTO data_sources 
                    (namespace, source_type, metadata, first_seen)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                """, (namespace, source_type, JSONMetadataParser.serialize_metadata(metadata)))
                await conn.commit()
        except Exception as e:
            logger.error(f"Error in async_register_data_source: {e}")
            raise
    
    async def async_get_active_namespaces(self) -> List[str]:
        """Async version of get_active_namespaces"""
        try:
            async with self.get_async_connection() as conn:
                async with conn.execute("""
                    SELECT namespace FROM data_sources 
                    WHERE is_active = TRUE
                    ORDER BY namespace
                """) as cursor:
                    rows = await cursor.fetchall()
                    return [row['namespace'] for row in rows]
        except Exception as e:
            logger.error(f"Error in async_get_active_namespaces: {e}")
            raise
    
    async def async_update_source_item_count(self, namespace: str):
        """Async version of update_source_item_count"""
        try:
            async with self.get_async_connection() as conn:
                async with conn.execute("""
                    SELECT COUNT(*) as count FROM data_items WHERE namespace = ?
                """, (namespace,)) as cursor:
                    count_row = await cursor.fetchone()
                    count = count_row['count']
                
                await conn.execute("""
                    UPDATE data_sources 
                    SET item_count = ?
                    WHERE namespace = ?
                """, (count, namespace))
                await conn.commit()
                
                return count
        except Exception as e:
            logger.error(f"Error in async_update_source_item_count: {e}")
            raise
    
    def __init__(self, db_path: str = "lifeboard.db"):
        self.db_path = db_path
        self._init_database()
        # Initialize cache for database stats
        self._stats_cache = None
        self._stats_cache_time = 0
        self._stats_cache_ttl = 5  # Cache TTL in seconds
        
    async def async_get_database_stats(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Async version of get_database_stats with caching
        :param force_refresh: If True, bypass the cache and force a fresh query
        """
        current_time = time.time()
        
        # Return cached results if they are still valid and force_refresh is False
        if (not force_refresh and 
            self._stats_cache is not None and 
            (current_time - self._stats_cache_time) < self._stats_cache_ttl):
            logger.debug("[TWITTER TRACE] Using cached database statistics")
            return self._stats_cache.copy()  # Return a copy to prevent cache modification
            
        start_time = current_time
        logger.info(f"[TWITTER TRACE] Database statistics query starting")
        
        try:
            async with self.get_async_connection() as conn:
                # Total items
                async with conn.execute("SELECT COUNT(*) as count FROM data_items") as cursor:
                    total_items_row = await cursor.fetchone()
                    total_items = total_items_row['count']
                
                # Items by namespace
                async with conn.execute("""
                    SELECT namespace, COUNT(*) as count 
                    FROM data_items 
                    GROUP BY namespace
                    ORDER BY count DESC
                """) as cursor:
                    namespace_rows = await cursor.fetchall()
                    namespace_counts = {row['namespace']: row['count'] for row in namespace_rows}
                
                # Embedding status
                async with conn.execute("""
                    SELECT embedding_status, COUNT(*) as count 
                    FROM data_items 
                    GROUP BY embedding_status
                """) as cursor:
                    embedding_rows = await cursor.fetchall()
                    embedding_status = {row['embedding_status']: row['count'] for row in embedding_rows}
                
                # Data sources
                async with conn.execute("SELECT COUNT(*) as count FROM data_sources WHERE is_active = TRUE") as cursor:
                    active_sources_row = await cursor.fetchone()
                    active_sources = active_sources_row['count']
                
                execution_time = (time.time() - start_time) * 1000
                
                # Create the stats dictionary
                stats = {
                    'total_items': total_items,
                    'namespace_counts': namespace_counts,
                    'embedding_status': embedding_status,
                    'active_sources': active_sources,
                    'database_path': self.db_path,
                    'database_size_mb': os.path.getsize(self.db_path) / (1024 * 1024) if os.path.exists(self.db_path) else 0
                }
                
                # Update the cache
                self._stats_cache = stats.copy()  # Store a copy to prevent cache modification
                self._stats_cache_time = current_time
                
                return stats
                
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            logger.error(f"[TWITTER TRACE] Database statistics failed after {execution_time:.2f}ms: {e}")
            logger.error(f"Error in async_get_database_stats: {e}")
            raise
    
    async def async_store_chat_message(self, user_message: str, assistant_response: str):
        """Async version of store_chat_message"""
        try:
            async with self.get_async_connection() as conn:
                await conn.execute("""
                    INSERT INTO chat_messages (user_message, assistant_response)
                    VALUES (?, ?)
                """, (user_message, assistant_response))
                await conn.commit()
        except Exception as e:
            logger.error(f"Error in async_store_chat_message: {e}")
            raise
    
    async def async_get_chat_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Async version of get_chat_history"""
        try:
            async with self.get_async_connection() as conn:
                async with conn.execute("""
                    SELECT id, user_message, assistant_response, timestamp
                    FROM chat_messages
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (limit,)) as cursor:
                    rows = await cursor.fetchall()
                    
                    messages = []
                    for row in rows:
                        messages.append({
                            'id': row['id'],
                            'user_message': row['user_message'],
                            'assistant_response': row['assistant_response'],
                            'timestamp': row['timestamp']
                        })
                    
                    # Return in chronological order (oldest first)
                    return list(reversed(messages))
        except Exception as e:
            logger.error(f"Error in async_get_chat_history: {e}")
            raise

    # Async versions of embedding and status operations
    
    async def async_update_embedding_status(self, id: str, status: str):
        """Async version of update_embedding_status"""
        try:
            async with self.get_async_connection() as conn:
                await conn.execute("""
                    UPDATE data_items 
                    SET embedding_status = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (status, id))
                await conn.commit()
        except Exception as e:
            logger.error(f"Error in async_update_embedding_status: {e}")
            raise
    
    async def async_update_ingestion_status(self, item_id: str, status: str):
        """Async version of update_ingestion_status"""
        start_time = time.time()
        
        # Check if this is a Twitter item for logging
        is_twitter_item = item_id.startswith('twitter:') if item_id else False
        
        if is_twitter_item:
            logger.info(f"[TWITTER TRACE] Database ingestion status update starting: item_id={item_id}, status={status}")
        
        try:
            async with self.get_async_connection() as conn:
                await conn.execute("""
                    UPDATE data_items
                    SET ingestion_status = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (status, item_id))
                await conn.commit()
                
                execution_time = (time.time() - start_time) * 1000
                
                if is_twitter_item:
                    logger.info(f"[TWITTER TRACE] Twitter ingestion status updated in {execution_time:.2f}ms: "
                               f"item_id={item_id}, new_status={status}")
                    
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            if is_twitter_item:
                logger.error(f"[TWITTER TRACE] Twitter ingestion status update failed after {execution_time:.2f}ms: {e}")
                logger.error(f"[TWITTER TRACE] Twitter status update error context: item_id={item_id}, status={status}")
            logger.error(f"Error in async_update_ingestion_status: {e}")
            raise
    
    async def async_get_pending_embeddings(self, limit: int = 100) -> List[Dict]:
        """Async version of get_pending_embeddings"""
        try:
            async with self.get_async_connection() as conn:
                async with conn.execute("""
                    SELECT id, namespace, source_id, content, metadata
                    FROM data_items 
                    WHERE embedding_status = 'pending'
                    ORDER BY created_at ASC
                    LIMIT ?
                """, (limit,)) as cursor:
                    rows = await cursor.fetchall()
                    
                    return DatabaseRowParser.parse_rows_with_metadata(
                        [dict(row) for row in rows]
                    )
        except Exception as e:
            logger.error(f"Error in async_get_pending_embeddings: {e}")
            raise

    
