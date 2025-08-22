import json
import logging
from typing import Any, Dict, List

from config.models import NewsConfig
from core.database import DatabaseService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
file_handler = logging.FileHandler("logs/news_service.log")
file_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
logger.addHandler(file_handler)


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
            # Get news from unified data_items table only
            news_items = self._get_news_from_data_items(date)
            logger.info(f"[NEWS SERVICE] Found {len(news_items)} items in 'data_items' table for date: {date}")

            # Debug logging to help diagnose empty results in Day View
            try:
                count = self.get_news_count_by_date(date)
                logger.info(f"[NEWS SERVICE] get_news_by_date: date={date} items_returned={len(news_items)} items_count={count}")
            except Exception as log_e:
                logger.error(f"[NEWS SERVICE] logging error in get_news_by_date for {date}: {log_e}")

            return news_items

        except Exception as e:
            logger.error(f"Error getting news by date {date}: {e}")
            return []

    def get_latest_news(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get the most recent news articles as fallback"""
        try:
            # Get latest news from unified data_items table only
            news_items = self._get_latest_from_data_items(limit)

            return news_items

        except Exception as e:
            logger.error(f"Error getting latest news: {e}")
            return []


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
                        metadata = {}

                news_items.append({
                    "title": metadata.get("title", (row["content"] or "")[:100] + "..."),
                    "link": metadata.get("link", row["source_id"]),
                    "snippet": metadata.get("snippet", ""),
                    "thumbnail_url": metadata.get("thumbnail_url"),
                    "published_datetime_utc": metadata.get("published_datetime_utc"),
                    "created_at": row["created_at"],
                    "content": row["content"],
                    "source": "data_items",
                })

            # Simple deterministic ordering: prefer published_datetime_utc if present
            try:
                news_items.sort(
                    key=lambda a: (a.get("published_datetime_utc") or "", a.get("created_at") or ""),
                    reverse=True,
                )
            except Exception:
                pass

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
                    "source": "data_items",
                })

            return news_items

    def get_news_count_by_date(self, date: str) -> int:
        """Get count of news articles for a specific date"""
        try:
            with self.db_service.get_connection() as conn:
                # Count from unified data_items table only
                cursor = conn.execute("""
                    SELECT COUNT(*) as count FROM data_items 
                    WHERE namespace = 'news' AND days_date = ?
                """, (date,))

                count = cursor.fetchone()["count"]

                return count

        except Exception as e:
            logger.error(f"Error getting news count for date {date}: {e}")
            return 0
