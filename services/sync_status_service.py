"""
Sync Status Service for tracking data source synchronization progress

This service provides real-time visibility into the synchronization status of all data sources,
allowing the frontend to display accurate progress information to users.
"""

import asyncio
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional, Set

from config.models import AppConfig
from core.base_service import BaseService

logger = logging.getLogger(__name__)


class SyncStatus(Enum):
    """Enumeration of possible sync statuses"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class SourceSyncInfo:
    """Information about a single source's sync status"""

    def __init__(self, namespace: str, source_type: str):
        self.namespace = namespace
        self.source_type = source_type
        self.status = SyncStatus.PENDING
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.last_updated: Optional[datetime] = None
        self.error_message: Optional[str] = None
        self.items_processed: int = 0
        self.items_stored: int = 0
        self.progress_percentage: float = 0.0

    def start_sync(self):
        """Mark sync as started"""
        self.status = SyncStatus.IN_PROGRESS
        self.started_at = datetime.now(timezone.utc)
        self.last_updated = self.started_at
        self.error_message = None
        logger.info(f"Sync started for {self.namespace}")

    def complete_sync(self, items_processed: int = 0, items_stored: int = 0):
        """Mark sync as completed"""
        self.status = SyncStatus.COMPLETED
        self.completed_at = datetime.now(timezone.utc)
        self.last_updated = self.completed_at
        self.items_processed = items_processed
        self.items_stored = items_stored
        self.progress_percentage = 100.0
        logger.info(f"Sync completed for {self.namespace}: {items_processed} processed, {items_stored} stored")

    def fail_sync(self, error_message: str):
        """Mark sync as failed"""
        self.status = SyncStatus.FAILED
        self.completed_at = datetime.now(timezone.utc)
        self.last_updated = self.completed_at
        self.error_message = error_message
        logger.error(f"Sync failed for {self.namespace}: {error_message}")

    def skip_sync(self, reason: str):
        """Mark sync as skipped"""
        self.status = SyncStatus.SKIPPED
        self.completed_at = datetime.now(timezone.utc)
        self.last_updated = self.completed_at
        self.error_message = reason
        logger.info(f"Sync skipped for {self.namespace}: {reason}")

    def update_progress(self, progress_percentage: float, items_processed: int = None):
        """Update sync progress"""
        self.progress_percentage = min(100.0, max(0.0, progress_percentage))
        if items_processed is not None:
            self.items_processed = items_processed
        self.last_updated = datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            "namespace": self.namespace,
            "source_type": self.source_type,
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
            "error_message": self.error_message,
            "items_processed": self.items_processed,
            "items_stored": self.items_stored,
            "progress_percentage": self.progress_percentage,
            "duration_seconds": self._calculate_duration(),
        }

    def _calculate_duration(self) -> Optional[float]:
        """Calculate sync duration in seconds"""
        if not self.started_at:
            return None
        end_time = self.completed_at or datetime.now(timezone.utc)
        return (end_time - self.started_at).total_seconds()


class SyncStatusService(BaseService):
    """Service for tracking and managing sync status of all data sources"""

    def __init__(self, config: AppConfig):
        super().__init__(service_name="SyncStatusService", config=config)
        self.sources: Dict[str, SourceSyncInfo] = {}
        self.global_sync_started_at: Optional[datetime] = None
        self.global_sync_completed_at: Optional[datetime] = None
        self.callbacks: Set[callable] = set()

        # Add capabilities
        self.add_capability("sync_tracking")
        self.add_capability("progress_monitoring")
        self.add_capability("real_time_updates")

    async def _initialize_service(self) -> bool:
        """Initialize the sync status service"""
        try:
            logger.info("Initializing SyncStatusService...")

            # Initialize known sources
            self._initialize_known_sources()

            logger.info("SyncStatusService initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize SyncStatusService: {e}")
            return False

    def _initialize_known_sources(self):
        """Initialize tracking for known data sources"""
        known_sources = [
            ("limitless", "limitless_api"),
            ("news", "news_api"),
            ("twitter", "twitter_archive"),
            ("weather", "weather_api"),
        ]

        for namespace, source_type in known_sources:
            self.sources[namespace] = SourceSyncInfo(namespace, source_type)
            logger.debug(f"Initialized sync tracking for {namespace} ({source_type})")

    def register_source(self, namespace: str, source_type: str):
        """Register a new source for sync tracking"""
        if namespace not in self.sources:
            self.sources[namespace] = SourceSyncInfo(namespace, source_type)
            logger.info(f"Registered new source for sync tracking: {namespace} ({source_type})")

    def start_global_sync(self):
        """Mark the start of global sync process"""
        self.global_sync_started_at = datetime.now(timezone.utc)
        self.global_sync_completed_at = None
        logger.info("Global sync process started")
        self._notify_callbacks("global_sync_started", {})

    def complete_global_sync(self):
        """Mark the completion of global sync process"""
        self.global_sync_completed_at = datetime.now(timezone.utc)
        logger.info("Global sync process completed")
        self._notify_callbacks("global_sync_completed", self.get_overall_status())

    def start_source_sync(self, namespace: str):
        """Mark the start of sync for a specific source"""
        if namespace in self.sources:
            self.sources[namespace].start_sync()
            self._notify_callbacks("source_sync_started", {
                "namespace": namespace,
                "status": self.sources[namespace].to_dict(),
            })
        else:
            logger.warning(f"Attempted to start sync for unknown source: {namespace}")

    def complete_source_sync(self, namespace: str, items_processed: int = 0, items_stored: int = 0):
        """Mark the completion of sync for a specific source"""
        if namespace in self.sources:
            self.sources[namespace].complete_sync(items_processed, items_stored)
            self._notify_callbacks("source_sync_completed", {
                "namespace": namespace,
                "status": self.sources[namespace].to_dict(),
            })
        else:
            logger.warning(f"Attempted to complete sync for unknown source: {namespace}")

    def fail_source_sync(self, namespace: str, error_message: str):
        """Mark the failure of sync for a specific source"""
        if namespace in self.sources:
            self.sources[namespace].fail_sync(error_message)
            self._notify_callbacks("source_sync_failed", {
                "namespace": namespace,
                "status": self.sources[namespace].to_dict(),
                "error": error_message,
            })
        else:
            logger.warning(f"Attempted to fail sync for unknown source: {namespace}")

    def skip_source_sync(self, namespace: str, reason: str):
        """Mark a source sync as skipped"""
        if namespace in self.sources:
            self.sources[namespace].skip_sync(reason)
            self._notify_callbacks("source_sync_skipped", {
                "namespace": namespace,
                "status": self.sources[namespace].to_dict(),
                "reason": reason,
            })
        else:
            logger.warning(f"Attempted to skip sync for unknown source: {namespace}")

    def update_source_progress(self, namespace: str, progress_percentage: float, items_processed: int = None):
        """Update progress for a specific source"""
        if namespace in self.sources:
            self.sources[namespace].update_progress(progress_percentage, items_processed)
            self._notify_callbacks("source_progress_updated", {
                "namespace": namespace,
                "progress": progress_percentage,
                "items_processed": items_processed,
            })
        else:
            logger.warning(f"Attempted to update progress for unknown source: {namespace}")

    def get_source_status(self, namespace: str) -> Optional[Dict[str, Any]]:
        """Get status for a specific source"""
        if namespace in self.sources:
            return self.sources[namespace].to_dict()
        return None

    def get_overall_status(self) -> Dict[str, Any]:
        """Get overall sync status including all sources"""
        completed_sources = sum(1 for s in self.sources.values()
                              if s.status in [SyncStatus.COMPLETED, SyncStatus.SKIPPED])
        failed_sources = sum(1 for s in self.sources.values() if s.status == SyncStatus.FAILED)
        in_progress_sources = sum(1 for s in self.sources.values() if s.status == SyncStatus.IN_PROGRESS)
        total_sources = len(self.sources)

        is_complete = completed_sources + failed_sources == total_sources
        is_in_progress = in_progress_sources > 0

        # Calculate overall progress
        if total_sources == 0:
            overall_progress = 100.0
        else:
            total_progress = sum(s.progress_percentage for s in self.sources.values())
            overall_progress = total_progress / total_sources

        return {
            "is_complete": is_complete,
            "is_in_progress": is_in_progress,
            "completed_sources": completed_sources,
            "failed_sources": failed_sources,
            "in_progress_sources": in_progress_sources,
            "total_sources": total_sources,
            "overall_progress": overall_progress,
            "global_started_at": self.global_sync_started_at.isoformat() if self.global_sync_started_at else None,
            "global_completed_at": self.global_sync_completed_at.isoformat() if self.global_sync_completed_at else None,
            "global_duration_seconds": self._calculate_global_duration(),
            "sources": {namespace: source.to_dict() for namespace, source in self.sources.items()},
        }

    def _calculate_global_duration(self) -> Optional[float]:
        """Calculate global sync duration in seconds"""
        if not self.global_sync_started_at:
            return None
        end_time = self.global_sync_completed_at or datetime.now(timezone.utc)
        return (end_time - self.global_sync_started_at).total_seconds()

    def add_status_callback(self, callback: callable):
        """Add a callback for sync status updates"""
        self.callbacks.add(callback)
        logger.debug(f"Added sync status callback: {callback.__name__}")

    def remove_status_callback(self, callback: callable):
        """Remove a callback for sync status updates"""
        self.callbacks.discard(callback)
        logger.debug(f"Removed sync status callback: {callback.__name__}")

    def _notify_callbacks(self, event_type: str, data: Dict[str, Any]):
        """Notify all registered callbacks of status updates"""
        for callback in self.callbacks.copy():  # Copy to avoid modification during iteration
            try:
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(callback(event_type, data))
                else:
                    callback(event_type, data)
            except Exception as e:
                logger.error(f"Error calling sync status callback {callback.__name__}: {e}")

    async def reset_all_sources(self):
        """Reset all sources to pending status (useful for testing)"""
        for source in self.sources.values():
            source.status = SyncStatus.PENDING
            source.started_at = None
            source.completed_at = None
            source.last_updated = None
            source.error_message = None
            source.items_processed = 0
            source.items_stored = 0
            source.progress_percentage = 0.0

        self.global_sync_started_at = None
        self.global_sync_completed_at = None
        logger.info("Reset all source sync statuses to pending")

    async def get_service_health(self) -> Dict[str, Any]:
        """Get health status of the sync status service"""
        return {
            "service_name": self.service_name,
            "is_ready": self.is_ready,
            "tracked_sources": len(self.sources),
            "active_callbacks": len(self.callbacks),
            "overall_status": self.get_overall_status(),
        }


# Global instance for easy access
_sync_status_service_instance: Optional[SyncStatusService] = None


def get_sync_status_service() -> Optional[SyncStatusService]:
    """Get the global sync status service instance"""
    return _sync_status_service_instance


def set_sync_status_service(service: SyncStatusService):
    """Set the global sync status service instance"""
    global _sync_status_service_instance
    _sync_status_service_instance = service


def clear_sync_status_service():
    """Clear the global sync status service instance"""
    global _sync_status_service_instance
    _sync_status_service_instance = None
