#!/usr/bin/env python3
"""
Test script for chat round summary logging functionality
"""

import asyncio
import sys
import os
import logging

# Add the project root to the path
sys.path.insert(0, os.path.dirname(__file__))

from services.chat_service import ChatService, ChatRoundSummary
from services.text_processing_service import TextProcessingService, TextProcessingConfig
from config.factory import create_production_config


def test_summary_data_structure():
    """Test the ChatRoundSummary dataclass"""
    print("=== Testing ChatRoundSummary Data Structure ===")
    
    summary = ChatRoundSummary(user_query="Test query")
    
    # Test initial state
    print(f"User query: {summary.user_query}")
    print(f"Limitless search: {summary.limitless_search}")
    print(f"Vector search: {summary.vector_search}")
    print(f"SQL search: {summary.sql_search}")
    print(f"LLM response: {summary.llm_response}")
    print(f"Total time: {summary.total_processing_time}")
    
    # Test setting data
    summary.limitless_search['content'] = "Sample limitless content"
    summary.vector_search['content'] = "Sample vector content"
    summary.sql_search['query'] = "SELECT * FROM data_items"
    summary.sql_search['results'] = "Found 5 results"
    summary.llm_response = "Sample LLM response"
    
    print("\nAfter setting data:")
    print(f"Limitless: {summary.limitless_search}")
    print(f"Vector: {summary.vector_search}")
    print(f"SQL: {summary.sql_search}")
    print(f"LLM: {summary.llm_response}")
    print()


def test_helper_methods():
    """Test helper methods for text processing"""
    print("=== Testing Helper Methods ===")
    
    # Mock a simple chat service with helper methods
    class MockChatService:
        def _truncate_text(self, text: str, max_length: int = 100) -> str:
            if not text:
                return ""
            text_str = str(text).strip()
            if len(text_str) <= max_length:
                return text_str
            return text_str[:max_length] + "..."
        
        def _extract_content_from_results(self, results, max_items: int = 3) -> str:
            if not results:
                return "No results found"
            
            content_pieces = []
            for i, result in enumerate(results[:max_items]):
                content = result.get('content', '')
                if content:
                    piece = self._truncate_text(content, 50)
                    content_pieces.append(piece)
            
            if content_pieces:
                combined = " | ".join(content_pieces)
                return self._truncate_text(combined, 100)
            else:
                return f"{len(results)} results (no content available)"
    
    service = MockChatService()
    
    # Test truncation
    long_text = "This is a very long text that should be truncated when it exceeds the maximum length specified"
    truncated = service._truncate_text(long_text, 50)
    print(f"Original: {long_text}")
    print(f"Truncated: {truncated}")
    
    # Test content extraction
    mock_results = [
        {'content': 'First result with some content here'},
        {'content': 'Second result with different content'},
        {'content': 'Third result with more content to test'}
    ]
    
    extracted = service._extract_content_from_results(mock_results)
    print(f"Extracted content: {extracted}")
    print()


def test_summary_format():
    """Test the summary logging format"""
    print("=== Testing Summary Format ===")
    
    # Create a sample summary
    summary = ChatRoundSummary(
        user_query="What meetings did I have with John about the project yesterday?"
    )
    
    # Fill with sample data
    summary.limitless_search['content'] = "Meeting with John at 2pm discussing Q4 project milestones and budget allocation for the marketing initiative"
    summary.vector_search['content'] = "Project discussion notes from quarterly planning meeting with team leads about resource allocation"
    summary.sql_search['query'] = "SELECT id, namespace, source_id, content, metadata, created_at, updated_at, (CASE WHEN content LIKE '%meeting%' THEN 1 ELSE 0 END + CASE WHEN content LIKE '%john%' THEN 1 ELSE 0 END) as keyword_score FROM data_items WHERE (content LIKE '%meeting%' OR content LIKE '%john%') ORDER BY keyword_score DESC, updated_at DESC LIMIT 5"
    summary.sql_search['results'] = "Found 12 matches including: Project kickoff meeting notes with detailed discussion points, John's feedback on quarterly targets"
    summary.llm_response = "Based on your personal data, I found several meetings with John about projects yesterday. The main meeting was at 2pm where you discussed Q4 project milestones and budget allocation."
    summary.total_processing_time = 2.145
    
    # Mock truncation method
    def truncate_text(text, max_length=100):
        if not text:
            return ""
        text_str = str(text).strip()
        if len(text_str) <= max_length:
            return text_str
        return text_str[:max_length] + "..."
    
    # Generate summary format
    separator = "*" * 39
    summary_text = f"""
{separator}
CHAT ROUND SUMMARY
{separator}
User query: {truncate_text(summary.user_query, 100)}

Steps executed:
1. Limitless API search: {summary.limitless_search.get('content', 'Not executed')}
2. Vector search: {truncate_text(summary.vector_search.get('content', 'Not executed'), 100)}
3. SQL search query: {truncate_text(summary.sql_search.get('query', 'Not executed'), 150)}
4. SQL search results: {truncate_text(summary.sql_search.get('results', 'No results'), 100)}

LLM Response: {truncate_text(summary.llm_response, 100)}
Total processing time: {summary.total_processing_time:.3f}s
{separator}
"""
    
    print(summary_text)


def test_configuration():
    """Test configuration loading"""
    print("=== Testing Configuration ===")
    
    try:
        config = create_production_config()
        text_config = config.text_processing
        
        print(f"Chat summary enabled: {text_config.enable_chat_round_summary}")
        print(f"Summary truncation length: {text_config.summary_text_truncation_length}")
        
        # Test with different configs
        custom_config = TextProcessingConfig(
            enable_chat_round_summary=False,
            summary_text_truncation_length=50
        )
        
        print(f"Custom config - enabled: {custom_config.enable_chat_round_summary}")
        print(f"Custom config - length: {custom_config.summary_text_truncation_length}")
        
    except Exception as e:
        print(f"Configuration test failed: {e}")
    
    print()


async def test_integration():
    """Test integration with actual services"""
    print("=== Testing Integration ===")
    
    try:
        # This is a basic integration test - would need actual services for full test
        config = create_production_config()
        
        # Test that TextProcessingService can be created with the config
        text_service = TextProcessingService(config.text_processing)
        
        print(f"Text processing service created successfully")
        print(f"Config loaded: {text_service.get_processing_stats()}")
        
        # Test summary creation
        summary = ChatRoundSummary(user_query="Test integration query")
        print(f"Summary created: {summary.user_query}")
        
    except Exception as e:
        print(f"Integration test failed: {e}")


def main():
    """Run all tests"""
    print("Chat Round Summary Logging Tests")
    print("=" * 50)
    
    test_summary_data_structure()
    test_helper_methods()
    test_summary_format()
    test_configuration()
    
    # Run async test
    asyncio.run(test_integration())
    
    print("=" * 50)
    print("All tests completed!")
    print()
    print("To see the summary logging in action:")
    print("1. Start the application: python api/server.py")
    print("2. Visit http://localhost:8000/chat")
    print("3. Send a chat message")
    print("4. Check the logs for the CHAT ROUND SUMMARY")


if __name__ == "__main__":
    main()