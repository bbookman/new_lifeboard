"""
LLMRepository for LLM-specific database operations

This repository handles operations specific to LLM functionality including
generated summaries caching, prompt management, and context building operations.
"""

import logging
import json
from typing import Dict, Any, Optional, List
from datetime import datetime


class LLMRepository:
    """
    Repository for LLM-specific database operations
    
    Handles operations for generated_summaries, prompt_settings, and context building
    from various data sources (news, weather, limitless data).
    """
    
    def __init__(self, database_service):
        """
        Initialize LLM repository with database service dependency
        
        Args:
            database_service: DatabaseService instance for database operations
        """
        self.database_service = database_service
        self.logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
    
    def _get_connection(self):
        """Get database connection from service"""
        return self.database_service.get_connection()
    
    # Generated Summaries Operations
    def get_cached_summary(self, days_date: str) -> Optional[str]:
        """
        Get cached daily summary if available
        
        Args:
            days_date: Date string for the summary
            
        Returns:
            Cached summary content or None if not found
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("""
                    SELECT content
                    FROM generated_summaries 
                    WHERE days_date = ? AND is_active = TRUE
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (days_date,))
                
                row = cursor.fetchone()
                if row:
                    return row['content']
                return None
                
        except Exception as e:
            self.logger.error(f"Error getting cached summary for {days_date}: {e}")
            return None
    
    async def async_get_cached_summary(self, days_date: str) -> Optional[str]:
        """Async version of get_cached_summary"""
        return self.get_cached_summary(days_date)
    
    def store_generated_summary(self, days_date: str, content: str, prompt_used: str) -> None:
        """
        Store generated summary content for caching
        
        Args:
            days_date: Date string for the summary
            content: Generated summary content
            prompt_used: Prompt template used for generation
        """
        try:
            with self._get_connection() as conn:
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
                self.logger.debug(f"Stored generated summary for {days_date}")
                
        except Exception as e:
            self.logger.error(f"Error storing generated summary for {days_date}: {e}")
            raise
    
    async def async_store_generated_summary(self, days_date: str, content: str, prompt_used: str) -> None:
        """Async version of store_generated_summary"""
        self.store_generated_summary(days_date, content, prompt_used)
    
    # Prompt Settings Operations
    def get_active_prompt_document_id(self, prompt_type: str = "daily_summary") -> Optional[str]:
        """
        Get the active prompt document ID for a specific prompt type
        
        Args:
            prompt_type: Type of prompt (default: "daily_summary")
            
        Returns:
            Document ID of active prompt or None if not found
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("""
                    SELECT ps.prompt_document_id
                    FROM prompt_settings ps
                    WHERE ps.setting_key LIKE ? 
                    AND ps.is_active = TRUE
                    ORDER BY ps.updated_at DESC
                    LIMIT 1
                """, (f"{prompt_type}_prompt_%",))
                
                row = cursor.fetchone()
                if row and row['prompt_document_id']:
                    return row['prompt_document_id']
                return None
                
        except Exception as e:
            self.logger.error(f"Error getting active prompt document ID for {prompt_type}: {e}")
            return None
    
    async def async_get_active_prompt_document_id(self, prompt_type: str = "daily_summary") -> Optional[str]:
        """Async version of get_active_prompt_document_id"""
        return self.get_active_prompt_document_id(prompt_type)
    
    # Context Building Operations
    def get_news_for_context(self, days_date: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get news headlines for context building
        
        Args:
            days_date: Date string to filter news
            limit: Maximum number of news items to return
            
        Returns:
            List of news items with title and snippet
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("""
                    SELECT title, snippet FROM news 
                    WHERE days_date = ? 
                    ORDER BY created_at DESC 
                    LIMIT ?
                """, (days_date, limit))
                
                return [dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            self.logger.error(f"Error getting news for context on {days_date}: {e}")
            return []
    
    async def async_get_news_for_context(self, days_date: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Async version of get_news_for_context"""
        return self.get_news_for_context(days_date, limit)
    
    def get_weather_for_context(self, days_date: str) -> Optional[Dict[str, Any]]:
        """
        Get weather data for context building
        
        Args:
            days_date: Date string to filter weather data
            
        Returns:
            Weather data dictionary or None if not found
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("""
                    SELECT response_json FROM weather 
                    WHERE days_date = ? 
                    ORDER BY created_at DESC 
                    LIMIT 1
                """, (days_date,))
                
                row = cursor.fetchone()
                if row and row['response_json']:
                    try:
                        return json.loads(row['response_json'])
                    except json.JSONDecodeError:
                        self.logger.warning(f"Could not decode weather JSON for {days_date}")
                        return None
                return None
                
        except Exception as e:
            self.logger.error(f"Error getting weather for context on {days_date}: {e}")
            return None
    
    async def async_get_weather_for_context(self, days_date: str) -> Optional[Dict[str, Any]]:
        """Async version of get_weather_for_context"""
        return self.get_weather_for_context(days_date)
    
    def get_activities_for_context(self, days_date: str, limit: int = 3) -> List[Dict[str, Any]]:
        """
        Get limitless/activity data for context building
        
        Args:
            days_date: Date string to filter activities
            limit: Maximum number of activity items to return
            
        Returns:
            List of activity items with content
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("""
                    SELECT content FROM data_items 
                    WHERE namespace = 'limitless' AND days_date = ? 
                    ORDER BY created_at DESC 
                    LIMIT ?
                """, (days_date, limit))
                
                return [dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            self.logger.error(f"Error getting activities for context on {days_date}: {e}")
            return []
    
    async def async_get_activities_for_context(self, days_date: str, limit: int = 3) -> List[Dict[str, Any]]:
        """Async version of get_activities_for_context"""
        return self.get_activities_for_context(days_date, limit)
    
    def build_daily_context(self, days_date: str) -> str:
        """
        Build complete daily context from all available sources
        
        Args:
            days_date: Date string for context building
            
        Returns:
            Formatted context string with news, weather, and activities
        """
        context_parts = [f"Date: {days_date}"]
        
        # Get news headlines
        news_items = self.get_news_for_context(days_date)
        if news_items:
            context_parts.append("News Headlines:")
            for item in news_items:
                context_parts.append(f"- {item['title']}")
                if item.get('snippet'):
                    context_parts.append(f"  {item['snippet']}")
        
        # Get weather data
        weather_data = self.get_weather_for_context(days_date)
        if weather_data and 'data' in weather_data and weather_data['data']:
            weather_info = weather_data['data'][0]
            context_parts.append(f"Weather: {weather_info.get('weather', 'N/A')}")
            if 'temperature' in weather_info:
                context_parts.append(f"Temperature: {weather_info['temperature']}°C")
        
        # Get limitless/activity data
        activity_items = self.get_activities_for_context(days_date)
        if activity_items:
            context_parts.append("Activities:")
            for item in activity_items:
                if item['content']:
                    # Truncate long content
                    content = item['content'][:200]
                    if len(item['content']) > 200:
                        content += "..."
                    context_parts.append(f"- {content}")
        
        return "\n".join(context_parts)
    
    async def async_build_daily_context(self, days_date: str) -> str:
        """Async version of build_daily_context"""
        return self.build_daily_context(days_date)