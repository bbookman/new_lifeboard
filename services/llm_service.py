"""
LLM Service for Daily Summary Generation

This service handles LLM-powered content generation, specifically for daily summaries.
It wraps the existing Ollama provider and manages prompt fetching, context building,
and content generation workflows.
"""

import logging
import asyncio
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from core.base_service import BaseService
from core.database import DatabaseService
from services.document_service import DocumentService
from services.template_processor import TemplateProcessor
from llm.factory import LLMProviderFactory
from llm.base import LLMResponse, LLMError
from config.models import AppConfig
from services.debug_mixin import ServiceDebugMixin
from core.database_debug import DebugDatabaseConnection

logger = logging.getLogger(__name__)


@dataclass
class LLMGenerationResult:
    """Result of LLM content generation"""
    content: str
    prompt_used: str
    model_info: Dict[str, Any]
    generation_time: float
    success: bool
    error_message: Optional[str] = None


class LLMService(BaseService, ServiceDebugMixin):
    """Service for LLM-powered content generation"""
    
    def __init__(self,
                 database: DatabaseService,
                 document_service: DocumentService,
                 config: AppConfig):
        BaseService.__init__(self, service_name="LLMService", config=config)
        ServiceDebugMixin.__init__(self, "llm_service")
        self.database = database
        self.document_service = document_service
        self.config = config
        
        # Set up database debug monitoring if path is available
        if hasattr(database, 'db_path'):
            self.debug_db = DebugDatabaseConnection(database.db_path)
        else:
            self.debug_db = None
        
        # Initialize template processor for resolving prompt variables
        self.template_processor = TemplateProcessor(
            database=database,
            config=config
        )
        
        # Initialize LLM provider
        self.llm_factory = LLMProviderFactory(config.llm_provider)
        self.llm_provider = None
        
        # Add dependencies and capabilities
        self.add_dependency("DatabaseService")
        self.add_dependency("DocumentService")
        self.add_capability("llm_generation")
        self.add_capability("daily_summary")
        self.add_capability("prompt_management")
        
        # Log service initialization
        self.log_service_call("__init__", {
            "has_database": database is not None,
            "has_document_service": document_service is not None,
            "debug_db_available": self.debug_db is not None,
            "llm_provider_config": config.llm_provider.provider_type.value if config.llm_provider else "none"
        })
    
    async def _initialize_service(self) -> bool:
        """Initialize the LLM service"""
        self.log_service_call("_initialize_service")
        
        init_start = time.time()
        try:
            # Initialize LLM provider
            provider_start = time.time()
            self.llm_provider = await self.llm_factory.get_active_provider()
            provider_duration = (time.time() - provider_start) * 1000
            
            self.log_service_performance_metric("llm_provider_init_duration", provider_duration, "ms")
            
            if not self.llm_provider:
                self.logger.warning("No LLM provider available - service will operate with limited functionality")
                self.log_service_performance_metric("llm_provider_available", 0, "count")
                return True  # Still allow service to start
            
            # Test LLM connectivity
            connectivity_start = time.time()
            is_available = await self.llm_provider.is_available()
            connectivity_duration = (time.time() - connectivity_start) * 1000
            
            self.log_service_performance_metric("llm_connectivity_test_duration", connectivity_duration, "ms")
            self.log_service_performance_metric("llm_provider_available", 1 if is_available else 0, "count")
            
            if not is_available:
                self.logger.warning("LLM provider not available - service will operate with limited functionality")
            else:
                self.logger.info(f"LLM provider '{self.llm_provider.provider_name}' is available")
                
                # Get available models for logging
                try:
                    models = await self.llm_provider.get_models()
                    self.log_service_performance_metric("llm_available_models", len(models), "count")
                except Exception as model_error:
                    self.log_service_error("_initialize_service_get_models", model_error, {})
            
            init_duration = (time.time() - init_start) * 1000
            self.log_service_performance_metric("llm_service_init_total_duration", init_duration, "ms")
            
            self.logger.info("LLMService initialized successfully")
            return True
            
        except Exception as e:
            self.log_service_error("_initialize_service", e, {})
            self.logger.error(f"Failed to initialize LLMService: {e}")
            return False
    
    async def _shutdown_service(self) -> bool:
        """Shutdown the LLM service"""
        try:
            self.logger.info("LLMService shutdown successfully")
            return True
        except Exception as e:
            self.logger.error(f"Error during LLMService shutdown: {e}")
            return False
    
    async def _check_service_health(self) -> Dict[str, Any]:
        """Check service health"""
        health_info = {
            "healthy": True,
            "llm_enabled": True  # LLM service is always enabled when initialized
        }
        
        try:
            if self.llm_provider:
                provider_available = await self.llm_provider.is_available()
                health_info.update({
                    "provider_name": self.llm_provider.provider_name,
                    "provider_available": provider_available
                })
                
                if provider_available:
                    # Get available models
                    models = await self.llm_provider.get_models()
                    health_info["available_models"] = models
            else:
                health_info["provider_available"] = False
                health_info["error"] = "No LLM provider configured"
                
        except Exception as e:
            health_info["healthy"] = False
            health_info["error"] = str(e)
        
        return health_info
    
    async def generate_daily_summary(self, 
                                   days_date: str,
                                   force_regenerate: bool = False) -> LLMGenerationResult:
        """Generate daily summary using selected prompt and daily data"""
        self.log_service_call("generate_daily_summary", {
            "days_date": days_date,
            "force_regenerate": force_regenerate
        })
        
        self.logger.info(f"Starting daily summary generation for date: {days_date}")
        start_time = datetime.now(timezone.utc)
        generation_start = time.time()
        
        try:
            # Check if LLM provider is available
            provider_check_start = time.time()
            if not self.llm_provider or not await self.llm_provider.is_available():
                self.logger.warning("LLM provider not available. Aborting generation.")
                self.log_service_performance_metric("llm_generation_aborted", 1, "count")
                return LLMGenerationResult(
                    content="",
                    prompt_used="",
                    model_info={},
                    generation_time=0.0,
                    success=False,
                    error_message="LLM provider not available"
                )
            
            provider_check_duration = (time.time() - provider_check_start) * 1000
            self.log_service_performance_metric("llm_provider_check_duration", provider_check_duration, "ms")
            
            # Get selected prompt with template resolution
            self.logger.debug("Retrieving selected prompt.")
            prompt_start = time.time()
            prompt_text = await self._get_selected_prompt(days_date)
            prompt_duration = (time.time() - prompt_start) * 1000
            
            self.log_service_performance_metric("llm_prompt_retrieval_duration", prompt_duration, "ms")
            
            if not prompt_text:
                self.logger.warning("No prompt selected for daily summary. Aborting.")
                self.log_service_performance_metric("llm_generation_no_prompt", 1, "count")
                return LLMGenerationResult(
                    content="",
                    prompt_used="",
                    model_info={},
                    generation_time=0.0,
                    success=False,
                    error_message="No prompt selected. Please configure a prompt in Settings."
                )
            
            self.logger.debug("Successfully retrieved prompt.")
            self.log_service_performance_metric("llm_prompt_length", len(prompt_text), "chars")
            
            # Build context from daily data
            self.logger.info("Building daily context...")
            context_start = time.time()
            context = await self._build_daily_context(days_date)
            context_duration = (time.time() - context_start) * 1000
            
            self.log_service_performance_metric("llm_context_build_duration", context_duration, "ms")
            self.log_service_performance_metric("llm_context_length", len(context), "chars")
            
            self.logger.info("Daily context built successfully.")
            self.logger.debug(f"Context for {days_date}:\n{context}")

            # Generate content using LLM
            self.logger.info(f"Sending request to LLM provider: {self.llm_provider.provider_name}")
            self.logger.debug(f"Complete prompt being sent to LLM:\n--- START PROMPT ---\n{prompt_text}\n--- START CONTEXT ---\n{context}\n--- END PROMPT ---")
            
            llm_request_start = time.time()
            
            # Log external API call
            self.log_external_api_call(
                service="llm_provider",
                endpoint="/generate_response",
                status_code=0,  # Will update after response
                duration=0      # Will update after response
            )
            
            llm_response = await self.llm_provider.generate_response(
                prompt=prompt_text,
                context=context,
                max_tokens=1000,  # Reasonable default for daily summaries
                temperature=0.7   # Balanced creativity/consistency
            )
            
            llm_request_duration = (time.time() - llm_request_start) * 1000
            generation_time = (datetime.now(timezone.utc) - start_time).total_seconds()
            
            # Log successful LLM API call
            self.log_external_api_call(
                service="llm_provider", 
                endpoint="/generate_response",
                status_code=200,
                duration=llm_request_duration
            )
            
            self.log_service_performance_metric("llm_request_duration", llm_request_duration, "ms")
            self.log_service_performance_metric("llm_response_length", len(llm_response.content), "chars")
            self.log_service_performance_metric("llm_tokens_used", llm_response.usage.get('total_tokens', 0) if llm_response.usage else 0, "tokens")
            
            self.logger.info(f"Received response from LLM provider in {generation_time:.2f} seconds.")

            # Store generated content for caching
            storage_start = time.time()
            await self._store_generated_content(days_date, llm_response.content, prompt_text)
            storage_duration = (time.time() - storage_start) * 1000
            
            self.log_service_performance_metric("llm_storage_duration", storage_duration, "ms")
            
            total_generation_duration = (time.time() - generation_start) * 1000
            self.log_service_performance_metric("llm_total_generation_duration", total_generation_duration, "ms")
            self.log_service_performance_metric("llm_generation_success", 1, "count")
            
            return LLMGenerationResult(
                content=llm_response.content,
                prompt_used=prompt_text,
                model_info={
                    "model": llm_response.model,
                    "provider": llm_response.provider,
                    "usage": llm_response.usage
                },
                generation_time=generation_time,
                success=True
            )
            
        except LLMError as e:
            generation_time = (datetime.now(timezone.utc) - start_time).total_seconds()
            self.log_service_error("generate_daily_summary_llm", e, {
                "days_date": days_date,
                "force_regenerate": force_regenerate,
                "error_type": "LLMError"
            })
            self.log_service_performance_metric("llm_generation_llm_error", 1, "count")
            
            self.logger.error(f"LLM error generating daily summary for {days_date}: {e}", exc_info=True)
            return LLMGenerationResult(
                content="",
                prompt_used=prompt_text if 'prompt_text' in locals() else "",
                model_info={},
                generation_time=generation_time,
                success=False,
                error_message=f"LLM generation failed: {str(e)}"
            )
        except Exception as e:
            generation_time = (datetime.now(timezone.utc) - start_time).total_seconds()
            self.log_service_error("generate_daily_summary", e, {
                "days_date": days_date,
                "force_regenerate": force_regenerate,
                "error_type": type(e).__name__
            })
            self.log_service_performance_metric("llm_generation_general_error", 1, "count")
            
            self.logger.error(f"Error generating daily summary for {days_date}: {e}", exc_info=True)
            return LLMGenerationResult(
                content="",
                prompt_used=prompt_text if 'prompt_text' in locals() else "",
                model_info={},
                generation_time=generation_time,
                success=False,
                error_message=f"Generation failed: {str(e)}"
            )
    
    async def get_cached_summary(self, days_date: str) -> Optional[str]:
        """Get cached daily summary if available"""
        self.log_service_call("get_cached_summary", {"days_date": days_date})
        
        self.logger.debug(f"Attempting to get cached summary for date: {days_date}")
        
        db_start = time.time()
        try:
            connection_context = self.debug_db.get_connection() if self.debug_db else self.database.get_connection()
            
            with connection_context as conn:
                cursor = conn.execute("""
                    SELECT content
                    FROM generated_summaries 
                    WHERE days_date = ? AND is_active = TRUE
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (days_date,))
                
                row = cursor.fetchone()
                
                db_duration = (time.time() - db_start) * 1000
                self.log_database_operation("SELECT", "generated_summaries", db_duration)
                
                if row:
                    self.logger.debug(f"Found active cached summary for {days_date}.")
                    self.log_service_performance_metric("llm_cache_hit", 1, "count")
                    self.log_service_performance_metric("llm_cached_content_length", len(row['content']), "chars")
                    return row['content']
                else:
                    self.logger.debug(f"No active cached summary found for {days_date}.")
                    self.log_service_performance_metric("llm_cache_miss", 1, "count")
                    return None
                
        except Exception as e:
            self.log_service_error("get_cached_summary", e, {"days_date": days_date})
            self.logger.error(f"Error getting cached summary for {days_date}: {e}", exc_info=True)
            return None
    
    async def _get_selected_prompt(self, target_date: str) -> Optional[str]:
        """Get the currently selected prompt for daily summaries with template resolution"""
        self.logger.info("Retrieving selected prompt for daily summary.")
        try:
            with self.database.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT ps.prompt_document_id
                    FROM prompt_settings ps
                    WHERE ps.setting_key = 'daily_summary_prompt' 
                    AND ps.is_active = TRUE
                    ORDER BY ps.updated_at DESC
                    LIMIT 1
                """)
                
                row = cursor.fetchone()
                if not row or not row['prompt_document_id']:
                    self.logger.warning("No 'daily_summary_prompt' setting found in database.")
                    return None
                
                prompt_id = row['prompt_document_id']
                self.logger.debug(f"Found prompt setting, document_id: {prompt_id}")

                # Get the prompt document
                document = self.document_service.get_document(prompt_id)
                if not document or document.document_type != 'prompt':
                    self.logger.warning(f"Selected prompt document not found or invalid: {prompt_id}")
                    return None
                
                self.logger.info(f"Successfully retrieved prompt document with ID: {document.id}")
                
                # Process template variables in the prompt
                self.logger.debug("Processing template variables in prompt...")
                resolved_template = self.template_processor.resolve_template(
                    content=document.content_md,
                    target_date=target_date
                )
                
                if resolved_template.errors:
                    self.logger.warning(f"Template resolution errors: {resolved_template.errors}")
                
                self.logger.debug(f"Template resolution complete. Variables resolved: {resolved_template.variables_resolved}")
                return resolved_template.resolved_content
                
        except Exception as e:
            self.logger.error(f"Error getting selected prompt: {e}", exc_info=True)
            return None
    
    async def _build_daily_context(self, days_date: str) -> str:
        """Build context from daily data (news, weather, activities, etc.)"""
        self.log_service_call("_build_daily_context", {"days_date": days_date})
        
        self.logger.info(f"Building daily context for date: {days_date}")
        context_start = time.time()
        
        try:
            context_parts = []
            news_items_count = 0
            weather_found = False
            activity_items_count = 0
            
            # Add date context
            context_parts.append(f"Date: {days_date}")
            
            # Get daily data from various sources
            db_start = time.time()
            connection_context = self.debug_db.get_connection() if self.debug_db else self.database.get_connection()
            
            with connection_context as conn:
                # Get news headlines
                news_query_start = time.time()
                self.logger.debug(f"Fetching news data for context.")
                cursor = conn.execute("""
                    SELECT title, snippet FROM news 
                    WHERE days_date = ? 
                    ORDER BY created_at DESC 
                    LIMIT 5
                """, (days_date,))
                news_items = cursor.fetchall()
                news_query_duration = (time.time() - news_query_start) * 1000
                
                news_items_count = len(news_items)
                self.log_database_operation("SELECT", "news", news_query_duration)
                
                if news_items:
                    self.logger.debug(f"Found {len(news_items)} news items.")
                    context_parts.append("News Headlines:")
                    for item in news_items:
                        context_parts.append(f"- {item['title']}")
                        if item['snippet']:
                            context_parts.append(f"  {item['snippet']}")
                else:
                    self.logger.debug(f"No news data found for {days_date}.")

                # Get weather data
                weather_query_start = time.time()
                self.logger.debug(f"Fetching weather data for context.")
                cursor = conn.execute("""
                    SELECT response_json FROM weather 
                    WHERE days_date = ? 
                    ORDER BY created_at DESC 
                    LIMIT 1
                """, (days_date,))
                weather_row = cursor.fetchone()
                weather_query_duration = (time.time() - weather_query_start) * 1000
                
                self.log_database_operation("SELECT", "weather", weather_query_duration)
                
                if weather_row:
                    weather_found = True
                    self.logger.debug("Found weather data.")
                    import json
                    try:
                        weather_data = json.loads(weather_row['response_json'])
                        if 'data' in weather_data and weather_data['data']:
                            weather_info = weather_data['data'][0]
                            context_parts.append(f"Weather: {weather_info.get('weather', 'N/A')}")
                            if 'temperature' in weather_info:
                                context_parts.append(f"Temperature: {weather_info['temperature']}°C")
                    except json.JSONDecodeError:
                        self.logger.warning(f"Could not decode weather JSON for {days_date}")
                        pass
                else:
                    self.logger.debug(f"No weather data found for {days_date}.")

                # Get limitless/activity data
                activity_query_start = time.time()
                self.logger.debug(f"Fetching limitless data for context.")
                cursor = conn.execute("""
                    SELECT processed_content FROM limitless 
                    WHERE days_date = ? 
                    ORDER BY created_at DESC 
                    LIMIT 3
                """, (days_date,))
                activity_items = cursor.fetchall()
                activity_query_duration = (time.time() - activity_query_start) * 1000
                
                activity_items_count = len(activity_items)
                self.log_database_operation("SELECT", "limitless", activity_query_duration)
                
                if activity_items:
                    self.logger.debug(f"Found {len(activity_items)} limitless items.")
                    context_parts.append("Activities:")
                    for item in activity_items:
                        if item['processed_content']:
                            # Truncate long content
                            content = item['processed_content'][:200]
                            if len(item['processed_content']) > 200:
                                content += "..."
                            context_parts.append(f"- {content}")
                else:
                    self.logger.debug(f"No limitless data found for {days_date}.")

            context_build_duration = (time.time() - context_start) * 1000
            final_context = "\n".join(context_parts)
            
            # Log context building metrics
            self.log_service_performance_metric("llm_context_news_items", news_items_count, "count")
            self.log_service_performance_metric("llm_context_weather_found", 1 if weather_found else 0, "count")
            self.log_service_performance_metric("llm_context_activity_items", activity_items_count, "count")
            self.log_service_performance_metric("llm_context_final_length", len(final_context), "chars")
            self.log_service_performance_metric("llm_context_total_duration", context_build_duration, "ms")

            self.logger.info(f"Finished building context for {days_date}.")
            return final_context
            
        except Exception as e:
            self.log_service_error("_build_daily_context", e, {"days_date": days_date})
            self.logger.error(f"Error building daily context for {days_date}: {e}", exc_info=True)
            return f"Date: {days_date}\nError: Unable to load daily context data."
    
    async def _store_generated_content(self, days_date: str, content: str, prompt_used: str):
        """Store generated content for caching"""
        self.log_service_call("_store_generated_content", {
            "days_date": days_date,
            "content_length": len(content),
            "prompt_length": len(prompt_used)
        })
        
        self.logger.info(f"Storing generated content for {days_date} in cache.")
        
        storage_start = time.time()
        try:
            connection_context = self.debug_db.get_connection() if self.debug_db else self.database.get_connection()
            
            with connection_context as conn:
                # Deactivate any existing summaries for this date
                self.logger.debug(f"Deactivating existing summaries for {days_date}.")
                deactivate_start = time.time()
                conn.execute("""
                    UPDATE generated_summaries 
                    SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP
                    WHERE days_date = ?
                """, (days_date,))
                deactivate_duration = (time.time() - deactivate_start) * 1000
                
                self.log_database_operation("UPDATE", "generated_summaries", deactivate_duration)
                
                # Insert new summary
                self.logger.debug(f"Inserting new summary for {days_date}.")
                insert_start = time.time()
                conn.execute("""
                    INSERT INTO generated_summaries 
                    (days_date, content, prompt_used, is_active, created_at, updated_at)
                    VALUES (?, ?, ?, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """, (days_date, content, prompt_used))
                insert_duration = (time.time() - insert_start) * 1000
                
                self.log_database_operation("INSERT", "generated_summaries", insert_duration)
                
                conn.commit()
                
                total_storage_duration = (time.time() - storage_start) * 1000
                
                self.log_service_performance_metric("llm_storage_total_duration", total_storage_duration, "ms")
                self.log_service_performance_metric("llm_content_stored", 1, "count")
                
                self.logger.info(f"Successfully cached new summary for {days_date}.")
                
        except Exception as e:
            self.log_service_error("_store_generated_content", e, {
                "days_date": days_date,
                "content_length": len(content)
            })
            self.logger.error(f"Error storing generated content for {days_date}: {e}", exc_info=True)
            # Don't raise - this is just caching, not critical
    
