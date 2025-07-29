import asyncio
from typing import Dict, Any, Optional, List, AsyncIterator
from datetime import datetime, timezone, timedelta
import logging

from sources.base import BaseSource, DataItem
from core.database import DatabaseService
from config.models import AppConfig

logger = logging.getLogger(__name__)

class SyncResult:
    """Result of a sync operation"""
    
    def __init__(self, namespace: str):
        self.namespace = namespace
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
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return None
    
    @property
    def success(self) -> bool:
        return len(self.errors) == 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "namespace": self.namespace,
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

class SyncManager:
    """Manages synchronization for all data sources"""
    
    def __init__(self, database: DatabaseService, app_config: AppConfig):
        self.database = database
        self.app_config = app_config
        self.sources: Dict[str, BaseSource] = {}
        self._current_results: Dict[str, SyncResult] = {}

    def register_source(self, source: BaseSource):
        self.sources[source.namespace] = source
        logger.info(f"Registered source: {source.namespace}")

    async def get_last_sync_time(self, namespace: str) -> Optional[datetime]:
        key = f"{namespace}_last_sync_timestamp"
        timestamp_str = self.database.get_setting(key)
        if timestamp_str:
            try:
                return datetime.fromisoformat(timestamp_str)
            except (ValueError, TypeError):
                logger.warning(f"Invalid last sync timestamp for {namespace}: {timestamp_str}")
        return None

    async def set_last_sync_time(self, namespace: str, timestamp: datetime):
        key = f"{namespace}_last_sync_timestamp"
        self.database.set_setting(key, timestamp.isoformat())

    async def get_last_sync_result(self, namespace: str) -> Optional[Dict[str, Any]]:
        key = f"{namespace}_last_sync_result"
        return self.database.get_setting(key)

    async def store_sync_result(self, result: SyncResult):
        key = f"{result.namespace}_last_sync_result"
        self.database.set_setting(key, result.to_dict())

    async def sync_source(self, namespace: str, force_full_sync: bool = False, limit: int = 1000) -> AsyncIterator[DataItem]:
        if namespace not in self.sources:
            logger.error(f"Source '{namespace}' not registered.")
            return

        source = self.sources[namespace]
        result = SyncResult(namespace)
        self._current_results[namespace] = result
        result.start_time = datetime.now(timezone.utc)

        try:
            last_sync_time = await self.get_last_sync_time(namespace)
            sync_start_time = last_sync_time - timedelta(hours=1) if last_sync_time else None

            if force_full_sync or last_sync_time is None:
                logger.info(f"Starting full sync for {namespace}")
            else:
                logger.info(f"Starting incremental sync for {namespace} from {sync_start_time}")

            async for item in source.fetch_items(since=sync_start_time, limit=limit):
                try:
                    result.items_processed += 1
                    # A bit of a hack for weather source
                    if namespace == 'weather':
                        yield item
                        continue

                    existing_items = self.database.get_data_items_by_ids([f"{namespace}:{item.source_id}"])
                    if not existing_items:
                        result.items_new += 1
                        yield item
                    else:
                        result.items_skipped += 1

                except Exception as e:
                    error_msg = f"Error processing item in {namespace}: {str(e)}"
                    logger.error(error_msg)
                    result.errors.append(error_msg)

            if result.success:
                await self.set_last_sync_time(namespace, result.start_time)

        except Exception as e:
            error_msg = f"Sync failed for {namespace}: {str(e)}"
            logger.error(error_msg)
            result.errors.append(error_msg)
        finally:
            result.end_time = datetime.now(timezone.utc)
            await self.store_sync_result(result)
            del self._current_results[namespace]
