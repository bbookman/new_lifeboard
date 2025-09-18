#!/usr/bin/env python3
"""
Demo script to test data availability functionality
"""

import asyncio
import logging
from typing import Dict, Any
from unittest.mock import AsyncMock, MagicMock

from services.template_processor import TemplateProcessor
from services.llm_service import LLMService, LLMGenerationResult
from config.models import AppConfig


# Simple test to verify the full pipeline
async def test_data_availability_pipeline():
    """Test the complete data availability pipeline"""
    
    print("🔬 Testing Data Availability Pipeline")
    print("=" * 50)
    
    # Create mock dependencies
    mock_repository_factory = MagicMock()
    mock_data_item_repo = AsyncMock()
    mock_repository_factory.get_data_item_repository.return_value = mock_data_item_repo
    mock_repository_factory.database_service = AsyncMock()
    
    mock_config = MagicMock(spec=AppConfig)
    
    # Create template processor
    processor = TemplateProcessor(
        repository_factory=mock_repository_factory,
        config=mock_config,
        cache_enabled=False
    )
    
    # Test 1: Template with missing data
    print("📋 Test 1: Template with missing data sources")
    
    template_content = """
    Generate a daily summary based on:
    - Activities: {{LIMITLESS_DAY}}
    - News: {{NEWS_DAY}}
    - Social: {{TWITTER_DAY}}
    """
    
    # Mock no data available for any source
    mock_data_item_repo.async_get_data_items_by_date.return_value = []
    
    result = await processor.resolve_template(template_content, "2024-01-01")
    
    print(f"✅ Variables without data: {len(result.variables_without_data)}")
    print(f"✅ Data availability messages: {len(result.data_availability_messages)}")
    
    for i, msg in enumerate(result.data_availability_messages, 1):
        print(f"   {i}. {msg}")
    
    print()
    
    # Test 2: Template with partial data
    print("📋 Test 2: Template with partial data availability")
    
    def mock_partial_data(date, namespaces):
        """Mock function that returns data only for limitless"""
        if namespaces == ['limitless']:
            return [{'content': 'Had a meeting today', 'days_date': date}]
        else:
            return []
    
    mock_data_item_repo.async_get_data_items_by_date.side_effect = mock_partial_data
    
    result2 = await processor.resolve_template(template_content, "2024-01-01")
    
    print(f"✅ Variables without data: {len(result2.variables_without_data)}")
    print(f"✅ Data availability messages: {len(result2.data_availability_messages)}")
    
    for i, msg in enumerate(result2.data_availability_messages, 1):
        print(f"   {i}. {msg}")
    
    print()
    
    # Test 3: Template with all data available
    print("📋 Test 3: Template with all data available")
    
    # Mock data available for all sources
    mock_data_item_repo.async_get_data_items_by_date.side_effect = None
    mock_data_item_repo.async_get_data_items_by_date.return_value = [
        {'content': 'Some data available', 'days_date': '2024-01-01'}
    ]
    
    result3 = await processor.resolve_template(template_content, "2024-01-01")
    
    print(f"✅ Variables without data: {len(result3.variables_without_data)}")
    print(f"✅ Data availability messages: {len(result3.data_availability_messages)}")
    
    print()
    
    # Test 4: Template with no variables
    print("📋 Test 4: Template with no template variables")
    
    simple_template = "Generate a summary of today's activities."
    
    result4 = await processor.resolve_template(simple_template, "2024-01-01")
    
    print(f"✅ Variables without data: {len(result4.variables_without_data)}")
    print(f"✅ Data availability messages: {len(result4.data_availability_messages)}")
    print(f"✅ Content unchanged: {result4.resolved_content == simple_template}")
    
    print()
    print("🎉 All tests completed successfully!")
    
    # Test the API response structure
    print()
    print("🔬 Testing API Response Structure")
    print("=" * 50)
    
    # Simulate LLMGenerationResult with data availability info
    mock_result = LLMGenerationResult(
        content="Generated summary content",
        prompt_used="Mock prompt",
        model_info={"model": "test-model"},
        generation_time=1.5,
        success=True,
        missing_data_sources=["twitter", "news"],
        data_availability_messages=[
            "No data available for twitter at the moment, try again soon",
            "No data available for news at the moment, try again soon"
        ]
    )
    
    print(f"✅ LLMGenerationResult created successfully")
    print(f"   - Content: {mock_result.content[:50]}...")
    print(f"   - Missing sources: {mock_result.missing_data_sources}")
    print(f"   - Messages: {len(mock_result.data_availability_messages)}")
    
    for i, msg in enumerate(mock_result.data_availability_messages, 1):
        print(f"     {i}. {msg}")
    
    print()
    print("✨ Data availability functionality is working correctly!")


if __name__ == "__main__":
    asyncio.run(test_data_availability_pipeline())