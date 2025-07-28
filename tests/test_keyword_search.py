#!/usr/bin/env python3
"""
Simple test script for keyword extraction and SQL search functionality
"""

import asyncio
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(__file__))

from services.text_processing_service import TextProcessingService, TextProcessingConfig


def test_keyword_extraction():
    """Test keyword extraction functionality"""
    print("=== Testing Keyword Extraction ===")
    
    # Create text processing service
    config = TextProcessingConfig(
        minimum_keyword_length=2,
        max_keywords_per_query=10,
        enable_stemming=True,
        keyword_search_mode="OR"
    )
    
    service = TextProcessingService(config)
    
    # Test cases
    test_cases = [
        "What meetings did I have with John yesterday?",
        "Find conversations about the marketing project",
        "Show me discussions with Sarah about budget planning",
        "Tell me about my call with the team lead",
        "Any notes from the quarterly review meeting?"
    ]
    
    for query in test_cases:
        keywords = service.extract_keywords(query)
        print(f"Query: {query}")
        print(f"Keywords: {keywords}")
        print(f"Count: {len(keywords)}")
        print()


def test_sql_generation():
    """Test SQL query generation logic"""
    print("=== Testing SQL Query Generation ===")
    
    # Simulate the SQL generation logic from ChatService
    keywords = ["meeting", "john", "project"]
    max_results = 10
    search_mode = "OR"
    
    # Create LIKE conditions for each keyword
    like_conditions = []
    score_conditions = []
    params = []
    
    for keyword in keywords:
        like_pattern = f"%{keyword}%"
        like_conditions.append("content LIKE ?")
        score_conditions.append("CASE WHEN content LIKE ? THEN 1 ELSE 0 END")
        params.extend([like_pattern, like_pattern])
    
    # Determine search logic (AND vs OR)
    where_operator = " AND " if search_mode == "AND" else " OR "
    where_clause = f"({where_operator.join(like_conditions)})"
    
    # Build scoring clause
    score_clause = " + ".join(score_conditions)
    
    # Complete SQL query
    sql_query = f"""
        SELECT id, namespace, source_id, content, metadata, created_at, updated_at,
               ({score_clause}) as keyword_score
        FROM data_items 
        WHERE {where_clause}
        ORDER BY keyword_score DESC, updated_at DESC
        LIMIT ?
    """
    
    params.append(max_results)
    
    print(f"Keywords: {keywords}")
    print(f"Search mode: {search_mode}")
    print(f"Generated SQL:")
    print(sql_query)
    print(f"Parameters: {params}")


def test_stemming():
    """Test stemming functionality"""
    print("=== Testing Stemming ===")
    
    config = TextProcessingConfig(
        minimum_keyword_length=2,
        max_keywords_per_query=20,
        enable_stemming=True
    )
    
    service = TextProcessingService(config)
    
    # Test words that should be stemmed
    test_words = [
        "running", "walked", "bigger", "quickly", "happiness",
        "development", "creation", "cities", "flies", "cats"
    ]
    
    for word in test_words:
        stemmed = service._apply_stemming(word)
        print(f"{word} -> {stemmed}")


def test_stop_words():
    """Test stop word filtering"""
    print("=== Testing Stop Word Filtering ===")
    
    config = TextProcessingConfig(
        minimum_keyword_length=2,
        max_keywords_per_query=20,
        enable_stemming=True,
        custom_stop_words=["custom1", "custom2"]
    )
    
    service = TextProcessingService(config)
    
    text = "The quick brown fox jumped over the lazy dog and custom1 word custom2"
    keywords = service.extract_keywords(text)
    
    print(f"Original text: {text}")
    print(f"Keywords after stop word filtering: {keywords}")
    print(f"Stop words count: {len(service.stop_words)}")


async def test_integration():
    """Test integration with configuration"""
    print("=== Testing Configuration Integration ===")
    
    from config.factory import create_production_config
    
    try:
        config = create_production_config()
        
        # Test that text processing config loads correctly
        text_config = config.text_processing
        print(f"Text processing config loaded:")
        print(f"  Min keyword length: {text_config.minimum_keyword_length}")
        print(f"  Max keywords: {text_config.max_keywords_per_query}")
        print(f"  Search mode: {text_config.keyword_search_mode}")
        print(f"  Stemming enabled: {text_config.enable_stemming}")
        
        # Create service with config
        service = TextProcessingService(text_config)
        
        # Test extraction
        keywords = service.extract_keywords("Find my meeting notes about project planning")
        print(f"Sample extraction: {keywords}")
        
    except Exception as e:
        print(f"Configuration test failed: {e}")


def main():
    """Run all tests"""
    print("Keyword Search Enhancement Tests")
    print("=" * 50)
    
    test_keyword_extraction()
    test_sql_generation()
    test_stemming()
    test_stop_words()
    
    # Run async test
    asyncio.run(test_integration())
    
    print("=" * 50)
    print("All tests completed!")


if __name__ == "__main__":
    main()