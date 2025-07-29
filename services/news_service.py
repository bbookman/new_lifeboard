import json
from typing import List, Dict, Any, Optional
from datetime import datetime

from core.database import DatabaseService
from config.models import NewsConfig

class NewsService:
    """Service for handling news data queries and operations"""
    
    def __init__(self, db_service: DatabaseService, config: NewsConfig = None):
        self.db_service = db_service
        self.config = config
        # Default to 5 if no config provided
        self.items_per_day = config.unique_items_per_day if config else 5

    def get_news_by_date(self, date: str) -> List[Dict[str, Any]]:
        """Get news articles for a specific date (YYYY-MM-DD format)"""
        try:
            # First try to get from the dedicated news table
            news_items = self._get_news_from_news_table(date)
            
            # If no items found, try the unified data_items table
            if not news_items:
                news_items = self._get_news_from_data_items(date)
            
            return news_items
            
        except Exception as e:
            print(f"Error getting news by date {date}: {e}")
            return []

    def get_latest_news(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get the most recent news articles as fallback"""
        try:
            # Try dedicated news table first
            news_items = self._get_latest_from_news_table(limit)
            
            # Fallback to data_items table
            if not news_items:
                news_items = self._get_latest_from_data_items(limit)
            
            return news_items
            
        except Exception as e:
            print(f"Error getting latest news: {e}")
            return []

    def _get_news_from_news_table(self, date: str) -> List[Dict[str, Any]]:
        """Query news from dedicated news table by date"""
        with self.db_service.get_connection() as conn:
            cursor = conn.execute("""
                SELECT title, link, snippet, thumbnail_url, published_datetime_utc, created_at
                FROM news 
                WHERE DATE(published_datetime_utc) = ? OR DATE(created_at) = ?
                ORDER BY published_datetime_utc DESC, created_at DESC
                LIMIT ?
            """, (date, date, self.items_per_day))
            
            news_items = []
            for row in cursor.fetchall():
                news_items.append({
                    "title": row["title"],
                    "link": row["link"],
                    "snippet": row["snippet"],
                    "thumbnail_url": row["thumbnail_url"],
                    "published_datetime_utc": row["published_datetime_utc"],
                    "created_at": row["created_at"],
                    "source": "news_table"
                })
            
            return news_items

    def _get_news_from_data_items(self, date: str) -> List[Dict[str, Any]]:
        """Query news from unified data_items table by date"""
        with self.db_service.get_connection() as conn:
            cursor = conn.execute("""
                SELECT id, source_id, content, metadata, created_at, days_date
                FROM data_items 
                WHERE namespace = 'news' AND days_date = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (date, self.items_per_day))
            
            news_items = []
            for row in cursor.fetchall():
                # Parse metadata to extract title and other fields
                metadata = {}
                if row["metadata"]:
                    try:
                        metadata = json.loads(row["metadata"])
                    except (json.JSONDecodeError, TypeError):
                        pass
                
                news_items.append({
                    "title": metadata.get("title", row["content"][:100] + "..."),
                    "link": metadata.get("link", row["source_id"]),
                    "snippet": metadata.get("snippet", ""),
                    "thumbnail_url": metadata.get("thumbnail_url"),
                    "published_datetime_utc": metadata.get("published_datetime_utc"),
                    "created_at": row["created_at"],
                    "content": row["content"],
                    "source": "data_items"
                })
            
            return news_items

    def _get_latest_from_news_table(self, limit: int) -> List[Dict[str, Any]]:
        """Get latest news from dedicated news table"""
        with self.db_service.get_connection() as conn:
            cursor = conn.execute("""
                SELECT title, link, snippet, thumbnail_url, published_datetime_utc, created_at
                FROM news 
                ORDER BY published_datetime_utc DESC, created_at DESC
                LIMIT ?
            """, (limit,))
            
            news_items = []
            for row in cursor.fetchall():
                news_items.append({
                    "title": row["title"],
                    "link": row["link"], 
                    "snippet": row["snippet"],
                    "thumbnail_url": row["thumbnail_url"],
                    "published_datetime_utc": row["published_datetime_utc"],
                    "created_at": row["created_at"],
                    "source": "news_table"
                })
            
            return news_items

    def _get_latest_from_data_items(self, limit: int) -> List[Dict[str, Any]]:
        """Get latest news from unified data_items table"""
        with self.db_service.get_connection() as conn:
            cursor = conn.execute("""
                SELECT id, source_id, content, metadata, created_at, days_date
                FROM data_items 
                WHERE namespace = 'news'
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,))
            
            news_items = []
            for row in cursor.fetchall():
                # Parse metadata to extract title and other fields
                metadata = {}
                if row["metadata"]:
                    try:
                        metadata = json.loads(row["metadata"])
                    except (json.JSONDecodeError, TypeError):
                        pass
                
                news_items.append({
                    "title": metadata.get("title", row["content"][:100] + "..."),
                    "link": metadata.get("link", row["source_id"]),
                    "snippet": metadata.get("snippet", ""),
                    "thumbnail_url": metadata.get("thumbnail_url"),
                    "published_datetime_utc": metadata.get("published_datetime_utc"),
                    "created_at": row["created_at"],
                    "content": row["content"],
                    "source": "data_items"
                })
            
            return news_items

    def get_news_count_by_date(self, date: str) -> int:
        """Get count of news articles for a specific date"""
        try:
            with self.db_service.get_connection() as conn:
                # Count from both tables
                cursor1 = conn.execute("""
                    SELECT COUNT(*) as count FROM news 
                    WHERE DATE(published_datetime_utc) = ? OR DATE(created_at) = ?
                """, (date, date))
                
                cursor2 = conn.execute("""
                    SELECT COUNT(*) as count FROM data_items 
                    WHERE namespace = 'news' AND days_date = ?
                """, (date,))
                
                count1 = cursor1.fetchone()["count"]
                count2 = cursor2.fetchone()["count"]
                
                return max(count1, count2)  # Return the higher count
                
        except Exception as e:
            print(f"Error getting news count for date {date}: {e}")
            return 0