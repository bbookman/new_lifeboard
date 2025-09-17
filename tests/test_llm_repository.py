"""
Tests for LLMRepository

Tests the LLM-specific repository operations including generated summaries,
prompt settings, and context building functionality.
"""

import pytest
import tempfile
import os
from datetime import datetime, timezone
from unittest.mock import Mock, patch
import json

from core.repositories.llm_repository import LLMRepository
from core.database import DatabaseService


class TestLLMRepository:
    """Test cases for LLMRepository"""
    
    @pytest.fixture
    def database_service(self):
        """Create a test database service with in-memory database"""
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            db_path = tmp_file.name
        
        try:
            # Create database service
            db_service = DatabaseService(db_path)
            
            # Initialize with basic schema
            with db_service.get_connection() as conn:
                # Create generated_summaries table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS generated_summaries (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        days_date TEXT NOT NULL,
                        content TEXT NOT NULL,
                        prompt_used TEXT,
                        is_active BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create prompt_settings table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS prompt_settings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        setting_key TEXT NOT NULL,
                        prompt_document_id TEXT,
                        is_active BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create news table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS news (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT NOT NULL,
                        snippet TEXT,
                        days_date TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create weather table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS weather (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        days_date TEXT NOT NULL,
                        response_json TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create data_items table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS data_items (
                        id TEXT PRIMARY KEY,
                        namespace TEXT NOT NULL,
                        source_id TEXT NOT NULL,
                        content TEXT,
                        metadata TEXT,
                        days_date TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                conn.commit()
            
            yield db_service
            
        finally:
            # Cleanup
            try:
                os.unlink(db_path)
            except FileNotFoundError:
                pass
    
    @pytest.fixture
    def llm_repository(self, database_service):
        """Create LLMRepository instance with test database"""
        return LLMRepository(database_service)
    
    def test_store_and_get_cached_summary(self, llm_repository):
        """Test storing and retrieving cached summaries"""
        days_date = "2025-09-17"
        content = "This is a test summary."
        prompt_used = "Test prompt template"
        
        # Store summary
        llm_repository.store_generated_summary(days_date, content, prompt_used)
        
        # Retrieve summary
        retrieved_content = llm_repository.get_cached_summary(days_date)
        
        assert retrieved_content == content
    
    def test_get_cached_summary_not_found(self, llm_repository):
        """Test retrieving non-existent cached summary"""
        result = llm_repository.get_cached_summary("2025-01-01")
        assert result is None
    
    def test_store_summary_deactivates_old(self, llm_repository):
        """Test that storing new summary deactivates old ones"""
        days_date = "2025-09-17"
        
        # Store first summary
        llm_repository.store_generated_summary(days_date, "First summary", "Prompt 1")
        
        # Store second summary
        llm_repository.store_generated_summary(days_date, "Second summary", "Prompt 2")
        
        # Should get the second summary
        retrieved = llm_repository.get_cached_summary(days_date)
        assert retrieved == "Second summary"
    
    def test_get_active_prompt_document_id(self, llm_repository, database_service):
        """Test retrieving active prompt document ID"""
        # Insert test prompt setting
        with database_service.get_connection() as conn:
            conn.execute("""
                INSERT INTO prompt_settings (setting_key, prompt_document_id, is_active)
                VALUES ('daily_summary_prompt_default', 'test-doc-id', TRUE)
            """)
            conn.commit()
        
        result = llm_repository.get_active_prompt_document_id("daily_summary")
        assert result == "test-doc-id"
    
    def test_get_active_prompt_document_id_not_found(self, llm_repository):
        """Test retrieving non-existent prompt document ID"""
        result = llm_repository.get_active_prompt_document_id("nonexistent")
        assert result is None
    
    def test_get_news_for_context(self, llm_repository, database_service):
        """Test retrieving news for context building"""
        days_date = "2025-09-17"
        
        # Insert test news items
        with database_service.get_connection() as conn:
            conn.execute("""
                INSERT INTO news (title, snippet, days_date)
                VALUES ('Test News 1', 'Test snippet 1', ?)
            """, (days_date,))
            conn.execute("""
                INSERT INTO news (title, snippet, days_date)
                VALUES ('Test News 2', 'Test snippet 2', ?)
            """, (days_date,))
            conn.commit()
        
        news_items = llm_repository.get_news_for_context(days_date)
        
        assert len(news_items) == 2
        assert news_items[0]['title'] == 'Test News 2'  # Should be ordered by created_at DESC
        assert news_items[1]['title'] == 'Test News 1'
    
    def test_get_weather_for_context(self, llm_repository, database_service):
        """Test retrieving weather for context building"""
        days_date = "2025-09-17"
        weather_data = {
            "data": [{
                "weather": "Sunny",
                "temperature": 25
            }]
        }
        
        # Insert test weather data
        with database_service.get_connection() as conn:
            conn.execute("""
                INSERT INTO weather (days_date, response_json)
                VALUES (?, ?)
            """, (days_date, json.dumps(weather_data)))
            conn.commit()
        
        result = llm_repository.get_weather_for_context(days_date)
        
        assert result == weather_data
        assert result['data'][0]['weather'] == 'Sunny'
        assert result['data'][0]['temperature'] == 25
    
    def test_get_activities_for_context(self, llm_repository, database_service):
        """Test retrieving activities for context building"""
        days_date = "2025-09-17"
        
        # Insert test activity data
        with database_service.get_connection() as conn:
            conn.execute("""
                INSERT INTO data_items (id, namespace, source_id, content, days_date)
                VALUES ('limitless:1', 'limitless', '1', 'Test activity 1', ?)
            """, (days_date,))
            conn.execute("""
                INSERT INTO data_items (id, namespace, source_id, content, days_date)
                VALUES ('limitless:2', 'limitless', '2', 'Test activity 2', ?)
            """, (days_date,))
            conn.commit()
        
        activities = llm_repository.get_activities_for_context(days_date)
        
        assert len(activities) == 2
        assert activities[0]['content'] == 'Test activity 2'  # Should be ordered by created_at DESC
        assert activities[1]['content'] == 'Test activity 1'
    
    def test_build_daily_context(self, llm_repository, database_service):
        """Test building complete daily context"""
        days_date = "2025-09-17"
        
        # Insert test data for all sources
        with database_service.get_connection() as conn:
            # News
            conn.execute("""
                INSERT INTO news (title, snippet, days_date)
                VALUES ('Breaking News', 'Important update', ?)
            """, (days_date,))
            
            # Weather
            weather_data = {"data": [{"weather": "Sunny", "temperature": 25}]}
            conn.execute("""
                INSERT INTO weather (days_date, response_json)
                VALUES (?, ?)
            """, (days_date, json.dumps(weather_data)))
            
            # Activities
            conn.execute("""
                INSERT INTO data_items (id, namespace, source_id, content, days_date)
                VALUES ('limitless:1', 'limitless', '1', 'Had a meeting', ?)
            """, (days_date,))
            
            conn.commit()
        
        context = llm_repository.build_daily_context(days_date)
        
        assert f"Date: {days_date}" in context
        assert "News Headlines:" in context
        assert "Breaking News" in context
        assert "Weather: Sunny" in context
        assert "Temperature: 25°C" in context
        assert "Activities:" in context
        assert "Had a meeting" in context
    
    @pytest.mark.asyncio
    async def test_async_methods(self, llm_repository):
        """Test that async methods work correctly"""
        days_date = "2025-09-17"
        content = "Async test summary"
        prompt_used = "Async test prompt"
        
        # Test async store and get
        await llm_repository.async_store_generated_summary(days_date, content, prompt_used)
        retrieved = await llm_repository.async_get_cached_summary(days_date)
        
        assert retrieved == content
        
        # Test async context building
        context = await llm_repository.async_build_daily_context(days_date)
        assert f"Date: {days_date}" in context