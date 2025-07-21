import asyncio
from typing import Dict, Any, Optional, List, AsyncIterator
from datetime import datetime, timezone, timedelta
import logging

from sources.limitless import LimitlessSource
from sources.base import DataItem
from core.database import DatabaseService
from config.models import LimitlessConfig

logger = logging.getLogger(__name__)


class SyncResult:
    """Result of a sync operation"""
    
    def __init__(self):
        self.items_processed = 0
        self.items_updated = 0
        self.items_new = 0
        self.items_skipped = 0
        self.errors: List[str] = []
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.last_processed_id: Optional[str] = None
        self.last_timestamp: Optional[datetime] = None
    
    @property
    def duration(self) -> Optional[timedelta]:
        """Get sync duration"""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return None
    
    @property
    def success(self) -> bool:
        """Check if sync was successful"""
        return len(self.errors) == 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            "items_processed": self.items_processed,
            "items_updated": self.items_updated,
            "items_new": self.items_new,
            "items_skipped": self.items_skipped,
            "errors": self.errors,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": self.duration.total_seconds() if self.duration else None,
            "success": self.success,
            "last_processed_id": self.last_processed_id,
            "last_timestamp": self.last_timestamp.isoformat() if self.last_timestamp else None
        }


class LimitlessSyncManager:
    """Manages incremental synchronization with Limitless API"""
    
    SETTINGS_LAST_SYNC = "limitless_last_sync_timestamp"
    SETTINGS_LAST_ID = "limitless_last_processed_id"
    SETTINGS_LAST_RESULT = "limitless_last_sync_result"
    
    def __init__(self, 
                 limitless_source: LimitlessSource,
                 database: DatabaseService,
                 config: LimitlessConfig):
        self.limitless_source = limitless_source
        self.database = database
        self.config = config
        self.overlap_hours = 1  # Fetch 1 hour before last sync to avoid missing data
    
    async def get_last_sync_time(self) -> Optional[datetime]:
        """Get the timestamp of the last successful sync"""
        timestamp_str = self.database.get_setting(self.SETTINGS_LAST_SYNC)
        if timestamp_str:
            try:
                return datetime.fromisoformat(timestamp_str)
            except (ValueError, TypeError):
                logger.warning(f"Invalid last sync timestamp: {timestamp_str}")
        return None
    
    async def set_last_sync_time(self, timestamp: datetime):
        """Store the timestamp of successful sync"""
        self.database.set_setting(self.SETTINGS_LAST_SYNC, timestamp.isoformat())
    
    async def get_last_processed_id(self) -> Optional[str]:
        """Get the ID of the last processed lifelog"""
        return self.database.get_setting(self.SETTINGS_LAST_ID)
    
    async def set_last_processed_id(self, lifelog_id: str):
        """Store the ID of the last processed lifelog"""
        self.database.set_setting(self.SETTINGS_LAST_ID, lifelog_id)
    
    async def get_last_sync_result(self) -> Optional[Dict[str, Any]]:
        """Get the result of the last sync operation"""
        return self.database.get_setting(self.SETTINGS_LAST_RESULT)
    
    async def store_sync_result(self, result: SyncResult):
        """Store sync result for monitoring and debugging"""
        self.database.set_setting(self.SETTINGS_LAST_RESULT, result.to_dict())
    
    def calculate_sync_start_time(self, last_sync: Optional[datetime]) -> Optional[datetime]:
        """Calculate the start time for incremental sync with overlap"""
        if last_sync is None:
            return None  # Full sync
        
        # Subtract overlap to ensure we don't miss any data
        return last_sync - timedelta(hours=self.overlap_hours)
    
    async def should_process_item(self, item: DataItem) -> bool:
        """Determine if an item should be processed (new or updated)"""
        # Check if item already exists in database
        existing_items = self.database.get_data_items_by_ids([f"limitless:{item.source_id}"])
        
        if not existing_items:
            return True  # New item
        
        existing_item = existing_items[0]
        
        # Compare update timestamps if available
        if item.updated_at and existing_item.get('updated_at'):
            try:
                existing_updated = datetime.fromisoformat(existing_item['updated_at'])
                # Process if the item has been updated since we last saw it
                return item.updated_at > existing_updated
            except (ValueError, TypeError):
                logger.warning(f"Invalid timestamp in existing item: {existing_item.get('updated_at')}")
        
        # If we can't compare timestamps, skip to avoid duplicates
        return False
    
    async def perform_incremental_sync(self, limit: int = 1000) -> AsyncIterator[DataItem]:
        """Perform incremental sync to get only new/updated items"""
        result = SyncResult()
        result.start_time = datetime.now(timezone.utc)
        self._current_result = result
        
        try:
            # Get last sync time and calculate start time with overlap
            last_sync = await self.get_last_sync_time()
            sync_start_time = self.calculate_sync_start_time(last_sync)
            
            logger.info(f"Starting incremental sync from {sync_start_time or 'beginning'}")
            
            # Fetch items from Limitless API
            processed_count = 0
            latest_timestamp = None
            
            async for item in self.limitless_source.fetch_items(since=sync_start_time, limit=limit):
                try:
                    result.items_processed += 1
                    
                    # Check if we should process this item
                    if await self.should_process_item(item):
                        # This is either a new item or an updated one
                        existing_items = self.database.get_data_items_by_ids([f"limitless:{item.source_id}"])
                        
                        if existing_items:
                            result.items_updated += 1
                            logger.debug(f"Updating existing item: {item.source_id}")
                        else:
                            result.items_new += 1
                            logger.debug(f"Processing new item: {item.source_id}")
                        
                        yield item  # Yield for processing by ingestion pipeline
                        
                        # Track latest timestamp and ID
                        if item.updated_at:
                            if latest_timestamp is None or item.updated_at > latest_timestamp:
                                latest_timestamp = item.updated_at
                                result.last_timestamp = latest_timestamp
                        
                        result.last_processed_id = item.source_id
                        
                    else:
                        result.items_skipped += 1
                        logger.debug(f"Skipping unchanged item: {item.source_id}")
                    
                    processed_count += 1
                    
                    # Update progress periodically
                    if processed_count % 100 == 0:
                        logger.info(f"Processed {processed_count} items...")
                        
                        # Store intermediate progress
                        if result.last_processed_id:
                            await self.set_last_processed_id(result.last_processed_id)
                    
                except Exception as e:
                    error_msg = f"Error processing item {item.source_id}: {str(e)}"
                    logger.error(error_msg)
                    result.errors.append(error_msg)
                    continue
            
            # Update sync timestamps on successful completion
            if result.success and result.items_processed > 0:
                sync_completion_time = datetime.now(timezone.utc)
                await self.set_last_sync_time(sync_completion_time)
                
                if result.last_processed_id:
                    await self.set_last_processed_id(result.last_processed_id)
                
                logger.info(f"Incremental sync completed: {result.items_new} new, "
                           f"{result.items_updated} updated, {result.items_skipped} skipped")
            
        except Exception as e:
            error_msg = f"Sync failed: {str(e)}"
            logger.error(error_msg)
            result.errors.append(error_msg)
        
        finally:
            result.end_time = datetime.now(timezone.utc)
            await self.store_sync_result(result)
    
    async def perform_full_sync(self, limit: int = 1000) -> AsyncIterator[DataItem]:
        """Perform full sync (for initial setup or recovery)"""
        result = SyncResult()
        result.start_time = datetime.now(timezone.utc)
        self._current_result = result
        
        try:
            logger.info("Starting full sync")
            
            processed_count = 0
            
            async for item in self.limitless_source.fetch_items(limit=limit):
                try:
                    result.items_processed += 1
                    
                    # In full sync, we process everything
                    existing_items = self.database.get_data_items_by_ids([f"limitless:{item.source_id}"])
                    
                    if existing_items:
                        result.items_updated += 1
                    else:
                        result.items_new += 1
                    
                    yield item
                    
                    result.last_processed_id = item.source_id
                    if item.updated_at:
                        result.last_timestamp = item.updated_at
                    
                    processed_count += 1
                    
                    if processed_count % 100 == 0:
                        logger.info(f"Processed {processed_count} items in full sync...")
                
                except Exception as e:
                    error_msg = f"Error processing item {item.source_id}: {str(e)}"
                    logger.error(error_msg)
                    result.errors.append(error_msg)
                    continue
            
            # Update sync state on successful completion
            if result.success:
                sync_completion_time = datetime.now(timezone.utc)
                await self.set_last_sync_time(sync_completion_time)
                
                if result.last_processed_id:
                    await self.set_last_processed_id(result.last_processed_id)
                
                logger.info(f"Full sync completed: {result.items_new} new, {result.items_updated} updated")
        
        except Exception as e:
            error_msg = f"Full sync failed: {str(e)}"
            logger.error(error_msg)
            result.errors.append(error_msg)
        
        finally:
            result.end_time = datetime.now(timezone.utc)
            await self.store_sync_result(result)
    
    async def sync(self, force_full_sync: bool = False, limit: int = 1000) -> AsyncIterator[DataItem]:
        """Perform sync operation (incremental by default, full if requested)"""
        last_sync = await self.get_last_sync_time()
        
        if force_full_sync or last_sync is None:
            async for item in self.perform_full_sync(limit=limit):
                yield item
        else:
            async for item in self.perform_incremental_sync(limit=limit):
                yield item
    
    def get_current_sync_result(self) -> Optional[SyncResult]:
        """Get the current sync result (for the ongoing sync)"""
        return getattr(self, '_current_result', None)
    
    async def get_sync_status(self) -> Dict[str, Any]:
        """Get current sync status information"""
        last_sync = await self.get_last_sync_time()
        last_result = await self.get_last_sync_result()
        last_id = await self.get_last_processed_id()
        
        return {
            "last_sync_time": last_sync.isoformat() if last_sync else None,
            "last_processed_id": last_id,
            "last_sync_result": last_result,
            "is_initial_sync": last_sync is None,
            "overlap_hours": self.overlap_hours,
            "next_sync_recommended": last_sync is None or 
                                   (datetime.now(timezone.utc) - last_sync).total_seconds() > 
                                   (self.config.sync_interval_hours * 3600)
        }