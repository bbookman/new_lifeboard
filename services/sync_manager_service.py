import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

from core.base_service import BaseService
from services.scheduler import AsyncScheduler
from services.ingestion import IngestionService, IngestionResult
from sources.base import BaseSource
from sources.limitless import LimitlessSource
from sources.news import NewsSource
from sources.weather import WeatherSource
from config.models import AppConfig

logger = logging.getLogger(__name__)


class SyncManagerService(BaseService):
    """Service that coordinates scheduled syncing of data sources"""
    
    def __init__(self, 
                 scheduler: AsyncScheduler,
                 ingestion_service: IngestionService,
                 config: AppConfig):
        super().__init__(service_name="SyncManagerService", config=config)
        self.scheduler = scheduler
        self.ingestion_service = ingestion_service
        self.source_job_mapping: Dict[str, str] = {}  # namespace -> job_id
        
        # Add dependencies and capabilities
        self.add_dependency("AsyncScheduler")
        self.add_dependency("IngestionService")
        self.add_capability("source_scheduling")
        self.add_capability("auto_sync")
        self.add_capability("job_management")
        
    async def register_source_for_auto_sync(self, source: BaseSource, force_full_sync: bool = False) -> bool:
        """Register a source for automatic scheduled syncing"""
        namespace = source.namespace
        
        # Check if source is already registered for auto-sync
        if namespace in self.source_job_mapping:
            logger.warning(f"Source {namespace} is already registered for auto-sync")
            return False
        
        # Determine sync interval
        if isinstance(source, LimitlessSource):
            interval_hours = self.config.limitless.sync_interval_hours
        elif isinstance(source, NewsSource):
            interval_hours = self.config.news.sync_interval_hours
        elif isinstance(source, WeatherSource):
            interval_hours = self.config.weather.sync_interval_hours
        else:
            # Default sync interval for other sources
            interval_hours = 24
        
        interval_seconds = interval_hours * 3600
        
        # Create sync function
        async def sync_function():
            """Async function to perform sync for this source"""
            import asyncio
            import traceback
            
            try:
                logger.info(f"SYNC_FUNCTION: Starting scheduled sync for {namespace}")
                logger.info(f"SYNC_FUNCTION: Current asyncio tasks before sync: {len(asyncio.all_tasks())}")
                
                # Add timeout protection
                try:
                    result = await asyncio.wait_for(
                        self.ingestion_service.ingest_from_source(
                            namespace=namespace,
                            force_full_sync=force_full_sync,
                            limit=1000
                        ),
                        timeout=300.0  # 5 minute timeout
                    )
                    
                    logger.info(f"SYNC_FUNCTION: Scheduled sync completed for {namespace}: "
                               f"{result.items_processed} processed, "
                               f"{result.items_stored} stored, "
                               f"{result.errors} errors")
                               
                    logger.info(f"SYNC_FUNCTION: Current asyncio tasks after sync: {len(asyncio.all_tasks())}")
                    return result.to_dict()
                               
                except asyncio.TimeoutError:
                    logger.error(f"SYNC_FUNCTION: Sync for {namespace} timed out after 5 minutes")
                    # Return a failure result instead of raising
                    return {"success": False, "error": "timeout", "items_processed": 0, "items_stored": 0}
                except Exception as sync_error:
                    logger.error(f"SYNC_FUNCTION: Sync operation failed for {namespace}: {sync_error}")
                    logger.error(f"SYNC_FUNCTION: Exception type: {type(sync_error).__name__}")
                    logger.error(f"SYNC_FUNCTION: Full traceback: {traceback.format_exc()}")
                    # Return a failure result instead of raising
                    return {"success": False, "error": str(sync_error), "items_processed": 0, "items_stored": 0}
                
            except Exception as e:
                logger.error(f"SYNC_FUNCTION: Scheduled sync failed for {namespace}: {e}")
                logger.error(f"SYNC_FUNCTION: Exception type: {type(e).__name__}")
                logger.error(f"SYNC_FUNCTION: Full traceback: {traceback.format_exc()}")
                
                # Don't re-raise the exception to prevent it from bubbling up and potentially
                # causing the server to shut down
                logger.error(f"SYNC_FUNCTION: Swallowing exception for {namespace} to prevent server shutdown")
                return {"success": False, "error": str(e), "items_processed": 0, "items_stored": 0}
        
        # Add job to scheduler
        job_id = self.scheduler.add_job(
            name=f"sync_{namespace}",
            namespace=namespace,
            func=sync_function,
            interval_seconds=interval_seconds,
            max_retries=3,
            timeout_seconds=self.config.scheduler.job_timeout_minutes * 60
        )
        
        # Track the mapping
        self.source_job_mapping[namespace] = job_id
        
        logger.info(f"Registered {namespace} for auto-sync every {interval_hours} hours (job_id: {job_id})")
        return True
    
    async def unregister_source_from_auto_sync(self, namespace: str) -> bool:
        """Unregister a source from automatic syncing"""
        job_id = self.source_job_mapping.get(namespace)
        if not job_id:
            logger.warning(f"Source {namespace} is not registered for auto-sync")
            return False
        
        # Remove job from scheduler
        success = self.scheduler.remove_job(job_id)
        if success:
            del self.source_job_mapping[namespace]
            logger.info(f"Unregistered {namespace} from auto-sync")
        
        return success
    
    async def trigger_immediate_sync(self, namespace: str, force_full_sync: bool = False) -> Optional[IngestionResult]:
        """Trigger immediate sync for a namespace"""
        try:
            logger.info(f"Triggering immediate sync for {namespace}")
            result = await self.ingestion_service.ingest_from_source(
                namespace=namespace,
                force_full_sync=force_full_sync,
                limit=1000
            )
            
            logger.info(f"Immediate sync completed for {namespace}: "
                       f"{result.items_processed} processed, "
                       f"{result.items_stored} stored")
            
            return result
            
        except Exception as e:
            logger.error(f"Immediate sync failed for {namespace}: {e}")
            raise
    
    async def trigger_scheduled_job(self, namespace: str) -> bool:
        """Trigger the scheduled job for a namespace immediately"""
        job_id = self.source_job_mapping.get(namespace)
        if not job_id:
            logger.warning(f"No scheduled job found for {namespace}")
            return False
        
        return await self.scheduler.trigger_job(job_id)
    
    def pause_source_sync(self, namespace: str) -> bool:
        """Pause automatic syncing for a source"""
        job_id = self.source_job_mapping.get(namespace)
        if not job_id:
            return False
        
        success = self.scheduler.pause_job(job_id)
        if success:
            logger.info(f"Paused auto-sync for {namespace}")
        
        return success
    
    def resume_source_sync(self, namespace: str) -> bool:
        """Resume automatic syncing for a source"""
        job_id = self.source_job_mapping.get(namespace)
        if not job_id:
            return False
        
        success = self.scheduler.resume_job(job_id)
        if success:
            logger.info(f"Resumed auto-sync for {namespace}")
        
        return success
    
    def get_source_sync_status(self, namespace: str) -> Optional[Dict[str, Any]]:
        """Get sync status for a specific source"""
        job_id = self.source_job_mapping.get(namespace)
        if not job_id:
            return None
        
        job_status = self.scheduler.get_job_status(job_id)
        if not job_status:
            return None
        
        # Enhance with source-specific information
        source_status = {
            "namespace": namespace,
            "job_id": job_id,
            "scheduler_status": job_status,
            "ingestion_status": self.ingestion_service.get_ingestion_status().get("source_stats", {}).get(namespace, {})
        }
        
        return source_status
    
    def get_all_sources_sync_status(self) -> Dict[str, Any]:
        """Get sync status for all registered sources"""
        all_jobs = self.scheduler.get_all_jobs_status()
        ingestion_status = self.ingestion_service.get_ingestion_status()
        
        # Organize by namespace
        sources_status = {}
        for namespace, job_id in self.source_job_mapping.items():
            job_status = all_jobs["jobs"].get(job_id, {})
            source_status = {
                "namespace": namespace,
                "job_id": job_id,
                "scheduler_status": job_status,
                "ingestion_status": ingestion_status.get("source_stats", {}).get(namespace, {})
            }
            sources_status[namespace] = source_status
        
        return {
            "sources": sources_status,
            "scheduler_summary": all_jobs["summary"],
            "ingestion_summary": {
                "total_sources": len(ingestion_status.get("registered_sources", [])),
                "database_stats": ingestion_status.get("database_stats", {}),
                "vector_store_stats": ingestion_status.get("vector_store_stats", {}),
                "pending_embeddings": ingestion_status.get("pending_embeddings", 0)
            }
        }
    
    async def auto_discover_and_register_sources(self) -> List[str]:
        """Auto-discover sources with valid configurations and register them for sync"""
        registered_sources = []
        
        # Check Limitless source
        if (self.config.limitless.api_key and 
            "limitless" in self.ingestion_service.sources):
            
            limitless_source = self.ingestion_service.sources["limitless"]
            success = await self.register_source_for_auto_sync(limitless_source)
            if success:
                registered_sources.append("limitless")
                logger.info("Auto-registered Limitless source for scheduled sync")
        else:
            logger.info("Limitless source not available for auto-sync (missing API key or not registered)")
        
        # Check News source
        if (self.config.news.enabled and self.config.news.api_key and 
            "news" in self.ingestion_service.sources):
            
            news_source = self.ingestion_service.sources["news"]
            success = await self.register_source_for_auto_sync(news_source)
            if success:
                registered_sources.append("news")
                logger.info("Auto-registered News source for scheduled sync")
        else:
            logger.info("News source not available for auto-sync (disabled or missing API key)")
        
        # Check Weather source
        if (self.config.weather.enabled and self.config.weather.api_key and 
            "weather" in self.ingestion_service.sources):
            
            weather_source = self.ingestion_service.sources["weather"]
            success = await self.register_source_for_auto_sync(weather_source)
            if success:
                registered_sources.append("weather")
                logger.info("Auto-registered Weather source for scheduled sync")
        else:
            logger.info("Weather source not available for auto-sync (disabled or missing API key)")
        
        # Check Twitter source (if configured)
        if "twitter" in self.ingestion_service.sources:
            twitter_source = self.ingestion_service.sources["twitter"]
            success = await self.register_source_for_auto_sync(twitter_source)
            if success:
                registered_sources.append("twitter")
                logger.info("Auto-registered Twitter source for scheduled sync")
        else:
            logger.info("Twitter source not available for auto-sync (not configured)")
        
        # Future: Add other source types here
        # if self.config.notion.api_key:
        #     ...
        
        logger.info(f"Auto-discovery completed. Registered {len(registered_sources)} sources: {registered_sources}")
        return registered_sources
    
    async def start_auto_sync(self) -> bool:
        """Start automatic syncing for all configured sources"""
        try:
            # Auto-discover and register sources
            registered_sources = await self.auto_discover_and_register_sources()
            
            if not registered_sources:
                logger.warning("No sources available for auto-sync")
                return False
            
            # Start the scheduler
            await self.scheduler.start()
            
            logger.info(f"Auto-sync started for {len(registered_sources)} sources")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start auto-sync: {e}")
            return False
    
    async def stop_auto_sync(self):
        """Stop automatic syncing"""
        await self.scheduler.stop()
        logger.info("Auto-sync stopped")
    
    async def _initialize_service(self) -> bool:
        """Initialize the sync manager service"""
        try:
            # Service is ready once all dependencies are injected
            # No additional initialization needed
            self.logger.info("SyncManagerService initialized successfully")
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize SyncManagerService: {e}")
            return False
    
    async def _shutdown_service(self) -> bool:
        """Shutdown the sync manager service"""
        try:
            await self.stop_auto_sync()
            self.logger.info("SyncManagerService shutdown successfully")
            return True
        except Exception as e:
            self.logger.error(f"Error during SyncManagerService shutdown: {e}")
            return False
    
    async def _check_service_health(self) -> Dict[str, Any]:
        """Check service health"""
        health_status = {
            "scheduler_running": self.scheduler.is_running,
            "registered_sources": len(self.source_job_mapping),
            "scheduler_stats": self.scheduler.stats,
            "issues": []
        }
        
        # Check for issues
        all_status = self.get_all_sources_sync_status()
        
        for namespace, status in all_status["sources"].items():
            job_status = status["scheduler_status"]
            
            # Check for repeatedly failing jobs
            if job_status.get("error_count", 0) >= 3:
                health_status["issues"].append({
                    "type": "repeated_failures",
                    "namespace": namespace,
                    "error_count": job_status["error_count"],
                    "last_error": job_status.get("last_error")
                })
            
            # Check for stale jobs (haven't run in 2x their interval)
            last_run = job_status.get("last_run")
            if last_run:
                last_run_dt = datetime.fromisoformat(last_run.replace('Z', '+00:00'))
                interval_seconds = job_status.get("interval_seconds", 3600)
                staleness_threshold = interval_seconds * 2
                
                if (datetime.now(timezone.utc) - last_run_dt).total_seconds() > staleness_threshold:
                    health_status["issues"].append({
                        "type": "stale_job",
                        "namespace": namespace,
                        "last_run": last_run,
                        "expected_interval_seconds": interval_seconds
                    })
        
        health_status["healthy"] = len(health_status["issues"]) == 0
        return health_status
    
    async def should_sync_on_startup(self, namespace: str) -> bool:
        """Check if a source should be synced on startup based on sync interval"""
        from datetime import datetime, timezone, timedelta
        
        # Get the last sync time from database
        last_sync_setting = self.ingestion_service.database.get_setting(f"{namespace}_last_sync")
        if not last_sync_setting:
            # Never synced before, should sync
            logger.info(f"Source {namespace} has never been synced, triggering startup sync")
            return True
        
        try:
            # Handle case where last_sync_setting might be a JSON object due to json_utils processing
            if isinstance(last_sync_setting, dict):
                if 'raw_value' in last_sync_setting:
                    actual_timestamp = last_sync_setting['raw_value']
                    logger.info(f"Extracting timestamp from raw_value structure for {namespace}: {actual_timestamp}")
                    last_sync_setting = actual_timestamp
                else:
                    logger.warning(f"Invalid timestamp structure for {namespace}: {last_sync_setting}, triggering sync")
                    return True
            
            # Ensure we have a string before parsing
            if not isinstance(last_sync_setting, str):
                logger.warning(f"Timestamp is not a string for {namespace}: {type(last_sync_setting)} = {last_sync_setting}, triggering sync")
                return True
            
            # Parse timestamp with better error handling for timezone issues
            last_sync_time = datetime.fromisoformat(last_sync_setting.replace('Z', '+00:00'))
            
            # Ensure timezone awareness
            if last_sync_time.tzinfo is None:
                logger.info(f"Adding UTC timezone to naive datetime for {namespace}")
                last_sync_time = last_sync_time.replace(tzinfo=timezone.utc)
                
        except (ValueError, TypeError) as e:
            # Invalid last sync time, should sync - Fixed logging format
            logger.warning(f"Invalid last sync time for {namespace}: '{last_sync_setting}' - Error: {e}, triggering sync")
            return True
        
        # Determine sync interval based on source type
        sync_interval_hours = 6  # Default
        
        if namespace == "limitless":
            sync_interval_hours = self.config.limitless.sync_interval_hours
        elif namespace == "news":
            sync_interval_hours = self.config.news.sync_interval_hours
        elif namespace == "weather":
            sync_interval_hours = self.config.weather.sync_interval_hours
        elif namespace == "twitter":
            # Twitter doesn't have a time-based sync interval, it syncs once
            return False
        else:
            logger.warning(f"Unknown namespace {namespace}, using default sync interval")
        
        # Check if enough time has passed
        time_since_last_sync = datetime.now(timezone.utc) - last_sync_time
        sync_interval_delta = timedelta(hours=sync_interval_hours)
        
        should_sync = time_since_last_sync >= sync_interval_delta
        
        if should_sync:
            logger.info(f"Source {namespace} last synced {time_since_last_sync.total_seconds()/3600:.1f} hours ago, "
                       f"interval is {sync_interval_hours} hours, triggering startup sync")
        else:
            remaining_time = sync_interval_delta - time_since_last_sync
            logger.info(f"Source {namespace} last synced {time_since_last_sync.total_seconds()/3600:.1f} hours ago, "
                       f"next sync in {remaining_time.total_seconds()/3600:.1f} hours")
        
        return should_sync
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on sync system (legacy method for backwards compatibility)"""
        return await self._check_service_health()