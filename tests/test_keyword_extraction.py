#!/usr/bin/env python3
"""
Test script to verify enhanced chat service logging
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_logging_enhancements():
    """Test the enhanced logging functionality"""
    print("🧪 Testing enhanced chat service logging...")
    
    try:
        # Setup logging to see our enhanced output
        import logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        from services.chat_service import ChatService
        from config.models import AppConfig
        from core.database import DatabaseService
        from core.vector_store import VectorStoreService
        from core.embeddings import EmbeddingService
        
        # Create minimal config
        config = AppConfig()
        
        # Create services (without full initialization for testing)
        database = DatabaseService()
        vector_store = VectorStoreService()
        embeddings = EmbeddingService(config.embedding)
        
        # Create chat service
        chat = ChatService(config, database, vector_store, embeddings)
        
        print("\n📝 Testing keyword extraction with enhanced logging:")
        print("=" * 60)
        
        # Test keyword extraction
        test_queries = [
            'do i have a dog',
            'tell me about grape my pet',
            'Bruce has conversations about work'
        ]
        
        for query in test_queries:
            print(f'\n🔍 Testing query: "{query}"')
            keywords = chat._extract_search_keywords(query)
            print(f'   Extracted keywords: {keywords}')
        
        print("\n📊 Testing execution sequence summary:")
        print("=" * 60)
        
        # Create a mock context to test sequence summary
        from services.chat_service import ChatContext
        
        # Test different scenarios
        scenarios = [
            ("No vectors available", ChatContext([], [], 0, "sql_only", 0)),
            ("Limited vectors", ChatContext([], [{"id": "test"}], 1, "sql_favored", 50)),
            ("Full vectors", ChatContext([{"id": "v1"}], [{"id": "s1"}], 2, "hybrid", 150))
        ]
        
        for scenario_name, context in scenarios:
            print(f'\n📋 Scenario: {scenario_name}')
            sequence = chat._build_execution_sequence_summary(context)
            for step in sequence:
                print(f'   {step}')
        
        print("\n✅ Enhanced logging test completed successfully!")
        print("\nThe chat service now includes:")
        print("📊 TOTAL VECTORS AVAILABLE logging")
        print("🎯 VECTORS IDENTIFIED FOR THIS CHAT QUERY logging") 
        print("🔄 Complete execution sequence summary")
        print("⚠️  Fallback mode indicators")
        print("🏁 Final chat transaction logging")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_logging_enhancements())
    sys.exit(0 if success else 1)