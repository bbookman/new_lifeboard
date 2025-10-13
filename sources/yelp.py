import logging
import hashlib
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup

from config.models import YelpConfig
from core.database import DatabaseService
from sources.base import BaseSource, DataItem

logger = logging.getLogger(__name__)


class YelpSource(BaseSource):
    """Yelp data source for processing Yelp review HTML files"""

    def __init__(self, config: YelpConfig, db_service: DatabaseService = None):
        super().__init__("yelp")
        self.config = config
        self.db_service = db_service or DatabaseService()

    async def process_html_content(self, html_content: str) -> Dict[str, Any]:
        """
        Process Yelp review data from HTML content.

        Args:
            html_content: HTML string content from user_review.html

        Returns:
            Dict with success, imported_count, message, and data_items
        """
        if not self.config.is_configured():
            logger.warning("[YELP] Yelp source not enabled. Skipping import.")
            return {
                "success": False,
                "imported_count": 0,
                "message": "Yelp source is not enabled in the configuration."
            }

        try:
            logger.info("[YELP] Starting Yelp review import from HTML content")

            # Parse HTML
            soup = BeautifulSoup(html_content, 'html.parser')

            # Find the table
            table = soup.find('table')
            if not table:
                logger.error("[YELP] No table found in HTML content")
                return {
                    "success": False,
                    "imported_count": 0,
                    "message": "No review table found in HTML file"
                }

            # Find all table rows (skip header)
            tbody = table.find('tbody')
            if not tbody:
                logger.error("[YELP] No tbody found in table")
                return {
                    "success": False,
                    "imported_count": 0,
                    "message": "Invalid table structure in HTML file"
                }

            rows = tbody.find_all('tr')
            logger.info(f"[YELP] Found {len(rows)} review rows in HTML")

            # Parse each review
            parsed_reviews = []
            for row in rows:
                cells = row.find_all('td')
                if len(cells) < 4:
                    logger.warning(f"[YELP] Skipping row with insufficient cells: {len(cells)}")
                    continue

                try:
                    # Extract data from cells
                    date_text = cells[0].get_text(strip=True)
                    business_name = cells[1].get_text(strip=True)
                    rating = cells[2].get_text(strip=True)
                    comment = cells[3].get_text(strip=True)

                    # Convert date to days_date format (YYYY-MM-DD)
                    try:
                        # Parse ISO datetime format: 2009-05-21T15:46:08+00:00
                        dt = datetime.fromisoformat(date_text.replace('+00:00', '+00:00'))
                        days_date = dt.strftime('%Y-%m-%d')
                    except (ValueError, AttributeError) as e:
                        logger.warning(f"[YELP] Could not parse date: {date_text}, error: {e}")
                        continue

                    # Create unique source_id using hash
                    source_data = f"{business_name}:{date_text}:{comment[:100]}"
                    source_id = hashlib.md5(source_data.encode()).hexdigest()

                    parsed_reviews.append({
                        'source_id': source_id,
                        'business_name': business_name,
                        'rating': rating,
                        'review_date': date_text,
                        'days_date': days_date,
                        'comment': comment
                    })

                except Exception as e:
                    logger.error(f"[YELP] Error parsing review row: {e}")
                    continue

            logger.info(f"[YELP] Successfully parsed {len(parsed_reviews)} reviews")

            if not parsed_reviews:
                return {
                    "success": True,
                    "imported_count": 0,
                    "message": "No valid reviews found in HTML file"
                }

            # Get existing reviews from database
            existing_source_ids = await self._get_existing_source_ids()
            logger.info(f"[YELP] Found {len(existing_source_ids)} existing reviews in database")

            # Filter out existing reviews
            new_reviews = [r for r in parsed_reviews if r['source_id'] not in existing_source_ids]
            logger.info(f"[YELP] Found {len(new_reviews)} new reviews to import")

            if not new_reviews:
                return {
                    "success": True,
                    "imported_count": 0,
                    "message": "Yelp reviews processed. No new reviews found to import."
                }

            # Transform reviews to DataItems
            data_items = self._transform_reviews_to_items(new_reviews)
            logger.info(f"[YELP] Transformed {len(data_items)} reviews to DataItems")

            return {
                "success": True,
                "imported_count": len(new_reviews),
                "message": f"Successfully imported {len(new_reviews)} new Yelp reviews.",
                "data_items": data_items
            }

        except Exception as e:
            logger.error(f"[YELP] Error processing Yelp HTML content: {e}", exc_info=True)
            return {
                "success": False,
                "imported_count": 0,
                "message": f"An error occurred during import: {e}"
            }

    async def _get_existing_source_ids(self) -> set:
        """Get existing Yelp source IDs from data_items table"""
        logger.debug(f"[YELP] Querying existing reviews: namespace={self.namespace}")

        existing_items = await self.db_service.async_get_data_items_by_namespace(
            self.namespace,
            limit=100000  # Large limit to get all existing reviews
        )
        existing_ids = {item['source_id'] for item in existing_items}

        logger.debug(f"[YELP] Database returned {len(existing_ids)} existing source IDs")
        return existing_ids

    def _transform_reviews_to_items(self, reviews: List[Dict[str, Any]]) -> List[DataItem]:
        """Transform review dicts to DataItem objects"""
        logger.debug(f"[YELP] Transforming {len(reviews)} reviews to DataItems")

        if not reviews:
            return []

        data_items = []
        for review in reviews:
            try:
                business_name = review.get('business_name', 'Unknown Business')
                comment = review.get('comment', '')

                # Build content string (excerpt of review)
                comment_excerpt = comment[:100] + "..." if len(comment) > 100 else comment
                content = f"Reviewed {business_name} - {comment_excerpt}"

                # Parse rating
                try:
                    rating_value = float(review.get('rating', 0))
                except (ValueError, TypeError):
                    rating_value = 0.0

                # Create DataItem
                data_item = DataItem(
                    namespace=self.namespace,
                    source_id=review['source_id'],
                    content=content,
                    metadata={
                        'business_name': business_name,
                        'rating': rating_value,
                        'review_date': review.get('review_date', ''),
                        'days_date': review.get('days_date', ''),
                        'comment': comment,
                        'source_origin': 'yelp_archive'
                    },
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc)
                )

                data_items.append(data_item)

            except Exception as e:
                logger.error(f"[YELP] Error creating DataItem for review {review.get('source_id', 'unknown')}: {e}")
                continue

        logger.debug(f"[YELP] Transformation complete: {len(data_items)} DataItems created")
        return data_items

    async def fetch_items(self, since: Optional[datetime] = None, limit: int = 100):
        """
        Fetch Yelp items from database.
        Yelp is an on-demand import source, so this fetches existing data.
        """
        logger.debug(f"[YELP] Fetching items: namespace={self.namespace}, limit={limit}")

        items = await self.db_service.async_get_data_items_by_namespace(self.namespace, limit)
        logger.debug(f"[YELP] Retrieved {len(items)} items from database")

        for item in items:
            # Filter by since if provided
            if since and item.get('created_at'):
                item_date = datetime.fromisoformat(item['created_at'])
                if item_date <= since:
                    continue

            # Parse metadata if it's a string
            metadata = item.get('metadata', {})
            if isinstance(metadata, str):
                import json
                try:
                    metadata = json.loads(metadata)
                except (json.JSONDecodeError, TypeError):
                    logger.warning(f"[YELP] Failed to parse metadata for item {item['source_id']}")
                    metadata = {}

            yield DataItem(
                namespace=item['namespace'],
                source_id=item['source_id'],
                content=item['content'],
                metadata=metadata,
                created_at=datetime.fromisoformat(item['created_at']) if item.get('created_at') else None,
                updated_at=datetime.fromisoformat(item['updated_at']) if item.get('updated_at') else None
            )

    async def get_item(self, source_id: str) -> Optional[DataItem]:
        """Get specific review by source ID"""
        logger.debug(f"[YELP] Getting specific item: source_id={source_id}")

        namespaced_id = f"{self.namespace}:{source_id}"
        items = await self.db_service.async_get_data_items_by_ids([namespaced_id])

        if not items:
            logger.debug(f"[YELP] Item not found: {source_id}")
            return None

        item = items[0]

        # Parse metadata if it's a string
        metadata = item.get('metadata', {})
        if isinstance(metadata, str):
            import json
            try:
                metadata = json.loads(metadata)
            except (json.JSONDecodeError, TypeError):
                logger.warning(f"[YELP] Failed to parse metadata for item {source_id}")
                metadata = {}

        return DataItem(
            namespace=item['namespace'],
            source_id=item['source_id'],
            content=item['content'],
            metadata=metadata,
            created_at=datetime.fromisoformat(item['created_at']) if item.get('created_at') else None,
            updated_at=datetime.fromisoformat(item['updated_at']) if item.get('updated_at') else None
        )

    def get_source_type(self) -> str:
        """Return the source type identifier"""
        return "yelp_archive"

    async def test_connection(self) -> bool:
        """Test if Yelp source is accessible"""
        return self.config.is_configured()
