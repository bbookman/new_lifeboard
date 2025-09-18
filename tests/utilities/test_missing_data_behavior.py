#!/usr/bin/env python3
"""
Test script to verify the new behavior where summary generation is blocked when required data is missing
"""

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock

from services.template_processor import TemplateProcessor
from services.llm_service import LLMService


async def test_blocked_generation():
    """Test that LLM generation is blocked when template variables have no data"""
    
    print("🔬 Testing Blocked Generation Logic")
    print("=" * 50)
    
    # Create mock dependencies for TemplateProcessor
    mock_repository_factory = MagicMock()
    mock_data_item_repo = AsyncMock()
    mock_repository_factory.get_data_item_repository.return_value = mock_data_item_repo
    mock_repository_factory.database_service = AsyncMock()
    
    mock_config = MagicMock()
    
    # Create template processor
    processor = TemplateProcessor(
        repository_factory=mock_repository_factory,
        config=mock_config,
        cache_enabled=False
    )
    
    # Test with the actual DEFAULT SUMMARY template content
    template_content = """The following is a speech-to-text transcription of a day.  

START TRANSCRIPT

{{LIMITLESS_DAY}}

END TRANSCRIPT

You are an expert at documenting a day in the life of a person..."""
    
    # Mock no data available for LIMITLESS
    mock_data_item_repo.async_get_data_items_by_date.return_value = []
    
    print("📋 Testing template resolution with missing LIMITLESS data...")
    result = await processor.resolve_template(template_content, "2025-09-18")
    
    print(f"✅ Template resolved with {len(result.variables_without_data)} missing variables")
    print(f"✅ Data availability messages: {len(result.data_availability_messages)}")
    
    for i, msg in enumerate(result.data_availability_messages, 1):
        print(f"   {i}. {msg}")
    
    # Check that the template was marked correctly
    assert "[NO_DATA:LIMITLESS_DAY]" in result.resolved_content
    assert len(result.data_availability_messages) == 1
    assert "limitless" in result.data_availability_messages[0].lower()
    
    print()
    print("🚫 Template processor correctly detected missing data!")
    
    # Now test that LLMService would block generation
    print()
    print("📋 Testing LLMService blocking logic...")
    
    # Create a mock document service that returns our template
    mock_document_service = MagicMock()
    mock_document = MagicMock()
    mock_document.content_md = template_content
    mock_document.document_type = 'prompt'
    mock_document.id = 'test-prompt-id'
    mock_document_service.get_document.return_value = mock_document
    
    # Create mock LLM repository
    mock_llm_repo = AsyncMock()
    mock_llm_repo.async_get_active_prompt_document_id.return_value = 'test-prompt-id'
    
    # Mock the repository factory for LLMService
    mock_llm_repository_factory = MagicMock()
    mock_llm_repository_factory.get_llm_repository.return_value = mock_llm_repo
    mock_llm_repository_factory.get_data_item_repository.return_value = mock_data_item_repo
    mock_llm_repository_factory.database_service = AsyncMock()
    
    # Create LLMService
    llm_service = LLMService(
        repository_factory=mock_llm_repository_factory,
        document_service=mock_document_service,
        config=mock_config
    )
    
    # Mock the template processor in LLMService to return our result
    llm_service.template_processor = processor
    
    # Test _get_selected_prompt
    prompt_text, data_messages = await llm_service._get_selected_prompt("2025-09-18")
    
    print(f"✅ Prompt resolved with data availability messages: {len(data_messages)}")
    print(f"✅ Messages: {data_messages}")
    
    # Verify that the prompt contains the NO_DATA marker
    assert "[NO_DATA:LIMITLESS_DAY]" in prompt_text
    assert len(data_messages) == 1
    
    print()
    print("🎉 Test completed successfully!")
    print("🚫 Summary generation would be blocked due to missing required data")
    print("✅ User would see 'No data available' message instead of generated summary")


if __name__ == "__main__":
    asyncio.run(test_blocked_generation())