"""
Twitter Rate Limit Service

Manages Twitter API rate limiting with configurable intervals and provides
status information for UI display.
"""

import logging
import math
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict
from core.database import DatabaseService

logger = logging.getLogger(__name__)


class TwitterRateLimitService:
    """Service to manage Twitter API rate limiting and status reporting with configurable intervals"""
    
    def __init__(self, db_service: DatabaseService, rate_limit_minutes: float = 15.0):
        self.db_service = db_service
        self.rate_limit_minutes = rate_limit_minutes
        self.twitter_namespace = "twitter"
    
    async def can_fetch_now(self) -> Tuple[bool, int]:
        """
        Check if a Twitter fetch is allowed now based on rate limiting.
        
        Returns:
            Tuple[bool, int]: (can_fetch, minutes_until_next_fetch)
        """
        try:
            last_fetch_time = await self._get_last_fetch_time()
            
            if not last_fetch_time:
                logger.info("[TWITTER TRACE] No previous fetch found, allowing fetch")
                return True, 0
            
            # Calculate time elapsed since last fetch
            now = datetime.utcnow()
            elapsed_seconds = (now - last_fetch_time).total_seconds()
            elapsed_minutes = elapsed_seconds / 60
            
            # Log the DB-stored last fetch timestamp
            last_fetch_iso = last_fetch_time.isoformat() if last_fetch_time else 'None'
            logger.debug(f"Last successful fetch (DB): {last_fetch_iso}")
            logger.debug(f"Elapsed minutes: {elapsed_minutes:.1f}, minutes remaining: {max(0, self.rate_limit_minutes - elapsed_minutes):.1f}")
            
            if elapsed_minutes >= self.rate_limit_minutes:
                logger.info(f"[TWITTER TRACE] {elapsed_minutes:.1f} minutes elapsed, allowing fetch")
                return True, 0
            else:
                minutes_remaining = int(math.ceil(max(0, self.rate_limit_minutes - elapsed_minutes)))
                logger.info(f"[TWITTER TRACE] Rate limited, {minutes_remaining} minutes remaining")
                return False, minutes_remaining
                
        except Exception as e:
            logger.error(f"[TWITTER TRACE] Error checking rate limit: {e}")
            # On error, allow the fetch to proceed
            return True, 0
    
    async def record_fetch_attempt(self, success: bool = True) -> None:
        """
        Record a Twitter fetch attempt.
        
        Args:
            success: Whether the fetch was successful. Only successful fetches
                    count against rate limits.
        """
        try:
            if success:
                now = datetime.utcnow()
                await self._update_last_fetch_time(now)
                logger.info(f"[TWITTER TRACE] Recorded successful fetch at {now.isoformat()}")
            else:
                logger.debug("Failed fetch not recorded for rate limiting")
                
        except Exception as e:
            logger.error(f"[TWITTER TRACE] Error recording fetch attempt: {e}")
    
    async def get_last_fetch_time(self) -> Optional[datetime]:
        """Get the last successful Twitter fetch time from database"""
        return await self._get_last_fetch_time()
    
    async def get_status_for_day(self, days_date: str) -> Optional[Dict[str, str]]:
        """
        Get Twitter fetch status information for a specific day.
        
        Args:
            days_date: Date in YYYY-MM-DD format
            
        Returns:
            Dict with status information or None if not applicable
        """
        try:
            last_fetch_time = await self._get_last_fetch_time()
            
            if not last_fetch_time:
                return None
            
            # Determine if this day should show Twitter status
            today = datetime.utcnow().strftime('%Y-%m-%d')
            yesterday = (datetime.utcnow() - timedelta(days=1)).strftime('%Y-%m-%d')
            
            # Only show status for today, yesterday, or recent days
            target_date = datetime.strptime(days_date, '%Y-%m-%d')
            now = datetime.utcnow()
            days_ago = (now.date() - target_date.date()).days
            
            if days_ago > 2:
                # For older days, show "Data complete" status
                return {
                    "status": f"Updated {self._format_time_ago(last_fetch_time)} • Data complete",
                    "icon": "✅",
                    "type": "complete"
                }
            
            # For recent days (today, yesterday, 2 days ago), show active status
            can_fetch, minutes_until = await self.can_fetch_now()
            
            if minutes_until > 0:
                status_text = f"Updated {self._format_time_ago(last_fetch_time)} • Checking for new tweets in {minutes_until} minutes or less"
            else:
                status_text = f"Updated {self._format_time_ago(last_fetch_time)} • Checking for new tweets in {int(self.rate_limit_minutes)} minutes or less"
            
            return {
                "status": status_text,
                "icon": "🔄",
                "type": "active",
                "minutes_until_next": minutes_until
            }
            
        except Exception as e:
            logger.error(f"[TWITTER TRACE] Error getting status for day {days_date}: {e}")
            return None
    
    async def _get_last_fetch_time(self) -> Optional[datetime]:
        """Get the last successful Twitter fetch time from database"""
        try:
            query = """
                SELECT last_synced 
                FROM data_sources 
                WHERE namespace = ? AND last_synced IS NOT NULL
            """
            result = await self.db_service.fetch_one(query, (self.twitter_namespace,))
            
            if result and result['last_synced']:
                return datetime.fromisoformat(result['last_synced'])
            return None
            
        except Exception as e:
            logger.error(f"[TWITTER TRACE] Error getting last fetch time: {e}")
            return None
    
    async def _update_last_fetch_time(self, fetch_time: datetime) -> None:
        """Update the last successful Twitter fetch time in database"""
        try:
            rows_affected = await self.db_service.execute_query(
                """
                UPDATE data_sources
                SET last_synced = ?
                WHERE namespace = ?
                """,
                (fetch_time.isoformat(), self.twitter_namespace)
            )
            if rows_affected == 0:
                # Insert fallback to ensure rate limit persistence for manual-only mode
                await self.db_service.execute_query(
                    """
                    INSERT INTO data_sources (namespace, source_type, last_synced)
                    VALUES (?, ?, ?)
                    """,
                    (self.twitter_namespace, 'twitter_api', fetch_time.isoformat())
                )
        except Exception as e:
            logger.error(f"[TWITTER TRACE] Error updating last fetch time: {e}")
            raise
    
    def _format_time_ago(self, time: datetime) -> str:
        """Format time difference as human-readable string"""
        try:
            now = datetime.utcnow()
            diff = now - time
            
            total_seconds = int(diff.total_seconds())
            
            if total_seconds < 60:
                return "just now"
            elif total_seconds < 3600:  # Less than 1 hour
                minutes = total_seconds // 60
                return f"{minutes} min ago"
            elif total_seconds < 86400:  # Less than 1 day
                hours = total_seconds // 3600
                return f"{hours}h ago"
            else:
                days = total_seconds // 86400
                return f"{days}d ago"
                
        except Exception as e:
            logger.error(f"[TWITTER TRACE] Error formatting time ago: {e}")
            return "unknown"