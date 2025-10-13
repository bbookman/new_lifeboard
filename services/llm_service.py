"""
LLM Service for Daily Summary Generation

This service handles LLM-powered content generation, specifically for daily summaries.
It wraps the existing Ollama provider and manages prompt fetching, context building,
and content generation workflows.
"""

import logging
import asyncio
import time
import re
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from core.base_service import BaseService
from core.database import DatabaseService
from core.repositories.repository_factory import RepositoryFactory
from services.document_service import DocumentService
from services.template_processor import TemplateProcessor
from llm.factory import LLMProviderFactory
from llm.base import LLMResponse, LLMError
from config.models import AppConfig
from services.debug_mixin import ServiceDebugMixin
from core.database_debug import DebugDatabaseConnection

logger = logging.getLogger(__name__)


def _extract_missing_sources_from_messages(messages: List[str]) -> List[str]:
    """Extract source names from data availability messages"""
    sources = []
    for message in messages:
        # Extract source name from message like "No data available for limitless at the moment, try again soon"
        if "No data available for " in message:
            # Extract text between "for " and " at the moment"
            start = message.find("for ") + 4
            end = message.find(" at the moment")
            if start > 3 and end > start:
                source = message[start:end].strip()
                sources.append(source)
    return sources


@dataclass
class LLMGenerationResult:
    """Result of LLM content generation with data availability info"""
    content: str
    prompt_used: str
    model_info: Dict[str, Any]
    generation_time: float
    success: bool
    error_message: Optional[str] = None
    missing_data_sources: List[str] = None
    data_availability_messages: List[str] = None


class LLMService(BaseService, ServiceDebugMixin):
    """Service for LLM-powered content generation"""
    
    def __init__(self,
                 repository_factory: RepositoryFactory,
                 document_service: DocumentService,
                 config: AppConfig):
        BaseService.__init__(self, service_name="LLMService", config=config)
        ServiceDebugMixin.__init__(self, "llm_service")
        self.repository_factory = repository_factory
        self.document_service = document_service
        self.config = config
        
        # Get repository instances
        self.llm_repo = repository_factory.get_llm_repository()
        self.data_item_repo = repository_factory.get_data_item_repository()
        
        # Keep backwards compatibility with database access for debug_db
        self.database = repository_factory.database_service
        
        # Set up database debug monitoring if path is available
        if hasattr(self.database, 'db_path'):
            self.debug_db = DebugDatabaseConnection(self.database.db_path)
        else:
            self.debug_db = None
        
        # Initialize template processor for resolving prompt variables
        self.template_processor = TemplateProcessor(
            repository_factory=repository_factory,
            config=config
        )
        
        # Initialize LLM provider
        self.llm_factory = LLMProviderFactory(config.llm_provider)
        self.llm_provider = None
        
        # Add dependencies and capabilities
        self.add_dependency("RepositoryFactory")
        self.add_dependency("DocumentService")
        self.add_capability("llm_generation")
        self.add_capability("daily_summary")
        self.add_capability("prompt_management")
        
        # Log service initialization
        self.log_service_call("__init__", {
            "has_repository_factory": repository_factory is not None,
            "has_document_service": document_service is not None,
            "debug_db_available": self.debug_db is not None,
            "llm_provider_config": config.llm_provider.provider if config.llm_provider else "none"
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
            
            # Get selected prompt with template resolution and data availability tracking
            self.logger.debug("Retrieving selected prompt.")
            prompt_start = time.time()
            prompt_text, data_availability_messages = await self._get_selected_prompt(days_date)
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
                    error_message="No prompt selected. Please configure a prompt in Settings.",
                    missing_data_sources=[],
                    data_availability_messages=[]
                )
            
            # Check if there are missing data sources - abort generation if so
            if data_availability_messages:
                self.logger.warning(f"Aborting summary generation due to missing required data sources: {data_availability_messages}")
                self.log_service_performance_metric("llm_generation_missing_data", 1, "count")
                return LLMGenerationResult(
                    content="",
                    prompt_used=prompt_text,
                    model_info={},
                    generation_time=0.0,
                    success=False,
                    error_message="Required data sources are not available for summary generation.",
                    missing_data_sources=_extract_missing_sources_from_messages(data_availability_messages),
                    data_availability_messages=data_availability_messages
                )

            # Defensive check: detect placeholder strings that indicate missing data
            # This catches edge cases where cache or other issues bypass the availability check
            if '[NO_DATA:' in prompt_text:
                self.logger.warning(f"Aborting summary generation: placeholder detected in resolved prompt")
                self.log_service_performance_metric("llm_generation_placeholder_detected", 1, "count")

                # Extract source names from placeholders
                placeholder_pattern = re.compile(r'\[NO_DATA:([A-Z_]+)_([A-Z]+)\]')
                missing_sources = []
                for match in placeholder_pattern.finditer(prompt_text):
                    source = match.group(1).lower().replace('_', ' ')
                    missing_sources.append(source)

                return LLMGenerationResult(
                    content="",
                    prompt_used=prompt_text,
                    model_info={},
                    generation_time=0.0,
                    success=False,
                    error_message="Required data sources are not available for summary generation.",
                    missing_data_sources=missing_sources,
                    data_availability_messages=[f"No data available for {src} at the moment, try again soon" for src in missing_sources]
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
                "llm_provider",
                "/generate_response",
                0,  # Will update after response
                0   # Will update after response
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
                "llm_provider", 
                "/generate_response",
                200,
                llm_request_duration
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
                success=True,
                missing_data_sources=[],  # Empty on success - data was available and generation completed
                data_availability_messages=[]  # Empty on success - no warnings needed when generation succeeds
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
                error_message=f"LLM generation failed: {str(e)}",
                missing_data_sources=[],
                data_availability_messages=[]
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
                error_message=f"Generation failed: {str(e)}",
                missing_data_sources=[],
                data_availability_messages=[]
            )
    
    async def get_cached_summary(self, days_date: str) -> Optional[str]:
        """Get cached daily summary if available"""
        self.log_service_call("get_cached_summary", {"days_date": days_date})
        
        self.logger.debug(f"Attempting to get cached summary for date: {days_date}")
        
        db_start = time.time()
        try:
            # Use repository method instead of direct database access
            content = await self.llm_repo.async_get_cached_summary(days_date)
            
            db_duration = (time.time() - db_start) * 1000
            self.log_database_operation("SELECT", "generated_summaries", db_duration)
            
            if content:
                self.logger.debug(f"Found active cached summary for {days_date}.")
                self.log_service_performance_metric("llm_cache_hit", 1, "count")
                self.log_service_performance_metric("llm_cached_content_length", len(content), "chars")
                return content
            else:
                self.logger.debug(f"No active cached summary found for {days_date}.")
                self.log_service_performance_metric("llm_cache_miss", 1, "count")
                return None
                
        except Exception as e:
            self.log_service_error("get_cached_summary", e, {"days_date": days_date})
            self.logger.error(f"Error getting cached summary for {days_date}: {e}", exc_info=True)
            return None
    
    async def _get_selected_prompt(self, target_date: str) -> tuple[Optional[str], List[str]]:
        """Get the currently selected prompt with data availability tracking"""
        self.logger.info("Retrieving selected prompt for daily summary.")
        try:
            # Use repository method to get prompt document ID
            prompt_id = await self.llm_repo.async_get_active_prompt_document_id("daily_summary")
            
            if not prompt_id:
                self.logger.warning("No daily summary prompt configured in database.")
                return None, []
            
            self.logger.debug(f"Found prompt setting, document_id: {prompt_id}")

            # Get the prompt document
            document = await self.document_service.get_document(prompt_id)
            if not document or document.document_type != 'prompt':
                self.logger.warning(f"Selected prompt document not found or invalid: {prompt_id}")
                return None, []
            
            self.logger.info(f"Successfully retrieved prompt document with ID: {document.id}")
            
            # Process template variables in the prompt
            self.logger.debug("Processing template variables in prompt...")
            resolved_template = await self.template_processor.resolve_template(
                content=document.content_md,
                target_date=target_date
            )
            
            if resolved_template.errors:
                self.logger.warning(f"Template resolution errors: {resolved_template.errors}")
            
            if resolved_template.data_availability_messages:
                self.logger.info(f"Data availability messages: {resolved_template.data_availability_messages}")
            
            self.logger.debug(f"Template resolution complete. Variables resolved: {resolved_template.variables_resolved}")
            return resolved_template.resolved_content, resolved_template.data_availability_messages
                
        except Exception as e:
            self.logger.error(f"Error getting selected prompt: {e}", exc_info=True)
            return None, []
    
    async def _build_daily_context(self, days_date: str) -> str:
        """Build context from daily data (news, weather, activities, etc.)"""
        self.log_service_call("_build_daily_context", {"days_date": days_date})
        
        self.logger.info(f"Building daily context for date: {days_date}")
        context_start = time.time()
        
        try:
            # Use repository method to build complete context
            context = await self.llm_repo.async_build_daily_context(days_date)
            
            context_build_duration = (time.time() - context_start) * 1000
            
            # Count items for logging
            news_items = await self.llm_repo.async_get_news_for_context(days_date)
            weather_data = await self.llm_repo.async_get_weather_for_context(days_date)
            activity_items = await self.llm_repo.async_get_activities_for_context(days_date)
            
            # Log context building metrics
            self.log_service_performance_metric("llm_context_news_items", len(news_items), "count")
            self.log_service_performance_metric("llm_context_weather_found", 1 if weather_data else 0, "count")
            self.log_service_performance_metric("llm_context_activity_items", len(activity_items), "count")
            self.log_service_performance_metric("llm_context_final_length", len(context), "chars")
            self.log_service_performance_metric("llm_context_total_duration", context_build_duration, "ms")

            self.logger.info(f"Finished building context for {days_date}.")
            return context
            
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
            # Use repository method to store generated content
            await self.llm_repo.async_store_generated_summary(days_date, content, prompt_used)
            
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
            # Don't raise - this is just caching, not critical
    
