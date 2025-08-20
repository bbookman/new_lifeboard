"""
LLM Service for Daily Summary Generation

This service handles LLM-powered content generation, specifically for daily summaries.
It wraps the existing Ollama provider and manages prompt fetching, context building,
and content generation workflows.
"""

import logging
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from core.base_service import BaseService
from core.database import DatabaseService
from services.document_service import DocumentService
from llm.factory import LLMProviderFactory
from llm.base import LLMResponse, LLMError
from config.models import AppConfig

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


class LLMService(BaseService):
    """Service for LLM-powered content generation"""
    
    def __init__(self,
                 database: DatabaseService,
                 document_service: DocumentService,
                 config: AppConfig):
        super().__init__(service_name="LLMService", config=config)
        self.database = database
        self.document_service = document_service
        self.config = config
        
        # Initialize LLM provider
        self.llm_factory = LLMProviderFactory(config.llm_provider)
        self.llm_provider = None
        
        # Add dependencies and capabilities
        self.add_dependency("DatabaseService")
        self.add_dependency("DocumentService")
        self.add_capability("llm_generation")
        self.add_capability("daily_summary")
        self.add_capability("prompt_management")
    
    async def _initialize_service(self) -> bool:
        """Initialize the LLM service"""
        try:
            # Initialize LLM provider
            self.llm_provider = await self.llm_factory.get_active_provider()
            
            if not self.llm_provider:
                self.logger.warning("No LLM provider available - service will operate with limited functionality")
                return True  # Still allow service to start
            
            # Test LLM connectivity
            is_available = await self.llm_provider.is_available()
            if not is_available:
                self.logger.warning("LLM provider not available - service will operate with limited functionality")
            else:
                self.logger.info(f"LLM provider '{self.llm_provider.provider_name}' is available")
            
            self.logger.info("LLMService initialized successfully")
            return True
            
        except Exception as e:
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
        start_time = datetime.now(timezone.utc)
        
        try:
            # Check if LLM provider is available
            if not self.llm_provider or not await self.llm_provider.is_available():
                return LLMGenerationResult(
                    content="",
                    prompt_used="",
                    model_info={},
                    generation_time=0.0,
                    success=False,
                    error_message="LLM provider not available"
                )
            
            # Get selected prompt
            prompt_text = await self._get_selected_prompt()
            if not prompt_text:
                return LLMGenerationResult(
                    content="",
                    prompt_used="",
                    model_info={},
                    generation_time=0.0,
                    success=False,
                    error_message="No prompt selected. Please configure a prompt in Settings."
                )
            
            # Build context from daily data
            context = await self._build_daily_context(days_date)
            
            # Generate content using LLM
            llm_response = await self.llm_provider.generate_response(
                prompt=prompt_text,
                context=context,
                max_tokens=1000,  # Reasonable default for daily summaries
                temperature=0.7   # Balanced creativity/consistency
            )
            
            generation_time = (datetime.now(timezone.utc) - start_time).total_seconds()
            
            # Store generated content for caching
            await self._store_generated_content(days_date, llm_response.content, prompt_text)
            
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
            logger.error(f"LLM error generating daily summary: {e}")
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
            logger.error(f"Error generating daily summary: {e}")
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
        try:
            with self.database.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT content
                    FROM generated_summaries 
                    WHERE days_date = ? AND is_active = TRUE
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (days_date,))
                
                row = cursor.fetchone()
                return row['content'] if row else None
                
        except Exception as e:
            logger.error(f"Error getting cached summary for {days_date}: {e}")
            return None
    
    async def _get_selected_prompt(self) -> Optional[str]:
        """Get the currently selected prompt for daily summaries"""
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
                    return None
                
                # Get the prompt document
                document = self.document_service.get_document(row['prompt_document_id'])
                if not document or document.document_type != 'prompt':
                    logger.warning(f"Selected prompt document not found or invalid: {row['prompt_document_id']}")
                    return None
                
                return document.content_md
                
        except Exception as e:
            logger.error(f"Error getting selected prompt: {e}")
            return None
    
    async def _build_daily_context(self, days_date: str) -> str:
        """Build context from daily data (news, weather, activities, etc.)"""
        try:
            context_parts = []
            
            # Add date context
            context_parts.append(f"Date: {days_date}")
            
            # Get daily data from various sources
            with self.database.get_connection() as conn:
                # Get news headlines
                cursor = conn.execute("""
                    SELECT title, snippet FROM news 
                    WHERE days_date = ? 
                    ORDER BY created_at DESC 
                    LIMIT 5
                """, (days_date,))
                news_items = cursor.fetchall()
                
                if news_items:
                    context_parts.append("News Headlines:")
                    for item in news_items:
                        context_parts.append(f"- {item['title']}")
                        if item['snippet']:
                            context_parts.append(f"  {item['snippet']}")
                
                # Get weather data
                cursor = conn.execute("""
                    SELECT response_json FROM weather 
                    WHERE days_date = ? 
                    ORDER BY created_at DESC 
                    LIMIT 1
                """, (days_date,))
                weather_row = cursor.fetchone()
                
                if weather_row:
                    import json
                    try:
                        weather_data = json.loads(weather_row['response_json'])
                        if 'data' in weather_data and weather_data['data']:
                            weather_info = weather_data['data'][0]
                            context_parts.append(f"Weather: {weather_info.get('weather', 'N/A')}")
                            if 'temperature' in weather_info:
                                context_parts.append(f"Temperature: {weather_info['temperature']}°C")
                    except json.JSONDecodeError:
                        pass
                
                # Get limitless/activity data
                cursor = conn.execute("""
                    SELECT processed_content FROM limitless 
                    WHERE days_date = ? 
                    ORDER BY created_at DESC 
                    LIMIT 3
                """, (days_date,))
                activity_items = cursor.fetchall()
                
                if activity_items:
                    context_parts.append("Activities:")
                    for item in activity_items:
                        if item['processed_content']:
                            # Truncate long content
                            content = item['processed_content'][:200]
                            if len(item['processed_content']) > 200:
                                content += "..."
                            context_parts.append(f"- {content}")
            
            return "\n".join(context_parts)
            
        except Exception as e:
            logger.error(f"Error building daily context for {days_date}: {e}")
            return f"Date: {days_date}\nError: Unable to load daily context data."
    
    async def _store_generated_content(self, days_date: str, content: str, prompt_used: str):
        """Store generated content for caching"""
        try:
            with self.database.get_connection() as conn:
                # Deactivate any existing summaries for this date
                conn.execute("""
                    UPDATE generated_summaries 
                    SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP
                    WHERE days_date = ?
                """, (days_date,))
                
                # Insert new summary
                conn.execute("""
                    INSERT INTO generated_summaries 
                    (days_date, content, prompt_used, is_active, created_at, updated_at)
                    VALUES (?, ?, ?, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """, (days_date, content, prompt_used))
                
                conn.commit()
                logger.debug(f"Stored generated summary for {days_date}")
                
        except Exception as e:
            logger.error(f"Error storing generated content for {days_date}: {e}")
            # Don't raise - this is just caching, not critical
    
